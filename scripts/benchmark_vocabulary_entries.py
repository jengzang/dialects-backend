"""Compare complete entries service results against a git baseline, read-only.

Run from the repository root with the project Python. --scale creates a disposable
growth fixture; it never modifies the input DB. No Redis/network/HTTP is timed.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.service.vocabulary.query import query_vocabulary_items


def baseline_query(ref):
    source = subprocess.check_output(
        ['git', 'show', f'{ref}:app/service/vocabulary/query.py'], cwd=ROOT,
        text=True,
    )
    module = ModuleType('_entries_benchmark_baseline')
    sys.modules[module.__name__] = module
    exec(compile(source, f'{ref}:query.py', 'exec'), module.__dict__)
    return module.query_vocabulary_items


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def growth_fixture(source, target, scale):
    """Duplicate original identities under disjoint users; preserve all indexes."""
    with readonly(source) as src, sqlite3.connect(target) as dest:
        src.backup(dest)
        dest.execute('ATTACH DATABASE ? AS original',
                     (source.resolve().as_uri() + '?mode=ro',))
        stride = dest.execute(
            'SELECT MAX(user_id) + 1 FROM ('
            'SELECT user_id FROM original.vocabulary_entries UNION ALL '
            'SELECT user_id FROM original.vocabulary_locations)'
        ).fetchone()[0]
        for copy in range(1, scale):
            for table in ('vocabulary_locations', 'vocabulary_entries'):
                columns = [row[1] for row in dest.execute(f'PRAGMA table_info({table})')
                           if row[1] != 'id']
                names = ', '.join(f'"{name}"' for name in columns)
                expressions = ', '.join('user_id + ?' if name == 'user_id'
                                        else f'"{name}"' for name in columns)
                dest.execute(f'INSERT INTO {table} ({names}) SELECT {expressions} '
                             f'FROM original.{table}', (copy * stride,))


def measure(path, old, rounds):
    conn = readonly(path)
    session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=conn))
    entries = conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0]
    province = conn.execute('SELECT province FROM vocabulary_locations '
                            "WHERE province IS NOT NULL AND province <> '' "
                            'GROUP BY province ORDER BY COUNT(*) DESC LIMIT 1').fetchone()[0]
    word = conn.execute('SELECT standard_word FROM vocabulary_entries '
                        "WHERE standard_word <> '' GROUP BY standard_word "
                        'ORDER BY COUNT(*) DESC LIMIT 1').fetchone()[0]
    scenarios = {
        'first-page': {},
        'deep-page': {'page': max(2, entries // 100)},
        'fuzzy-hit': {'q': '什么'},
        'fuzzy-no-hit': {'q': '不可能命中_8f0b7e4d9a'},
        'out-of-range': {'page': entries // 50 + 2},
        'province': {'province': province},
        'province-no-hit': {'province': '不可能省份_8f0b7e4d9a'},
        'exact-word': {'standard_words': [word]},
    }
    report = {'entries': entries, 'locations': conn.execute(
        'SELECT COUNT(*) FROM vocabulary_locations').fetchone()[0], 'results': []}
    for name, params in scenarios.items():
        for cached in (False, True):
            counts = {}
            def count_loader(sql, values):
                key = (sql, tuple(values))
                if key not in counts:
                    counts[key] = conn.execute(sql, values).fetchone()[0]
                return counts[key]
            options = dict(params)
            if cached:
                options['_count_loader'] = count_loader
            functions = {'old': old, 'new': query_vocabulary_items}
            if cached:
                # Both EXPLAIN captures, not just timed runs, must start with
                # a warm count resolver. Otherwise only old captures COUNT.
                for function in functions.values():
                    function(session=session, **options)
            expected = None
            plans = {}
            for version, function in functions.items():
                statements = []
                conn.set_trace_callback(statements.append)
                result = function(session=session, **options)
                conn.set_trace_callback(None)
                payload = json.dumps(asdict(result), ensure_ascii=False, sort_keys=True)
                if expected is None:
                    expected = payload
                assert payload == expected, (name, cached, version)
                plans[version] = [
                    {'sql': sql, 'plan': conn.execute('EXPLAIN QUERY PLAN ' + sql).fetchall()}
                    for sql in statements if sql.startswith('SELECT')
                ]
                # Warm SQLite caches for both plans. Cached mode is an ideal
                # exact-count cache hit, excluding Redis round trips.
                function(session=session, **options)
            samples = {'old': [], 'new': []}
            for iteration in range(rounds):
                order = ('old', 'new') if iteration % 2 == 0 else ('new', 'old')
                for version in order:
                    start = time.perf_counter()
                    result = functions[version](session=session, **options)
                    samples[version].append((time.perf_counter() - start) * 1000)
                    # Consume and check every returned field outside timed work.
                    assert json.dumps(asdict(result), ensure_ascii=False, sort_keys=True) == expected
            summary = {version: {
                'median_ms': statistics.median(times), 'min_ms': min(times),
                'max_ms': max(times), 'samples_ms': times,
            } for version, times in samples.items()}
            improvement = (1 - summary['new']['median_ms'] / summary['old']['median_ms']) * 100
            row = {'scenario': name, 'count_cache_hit': cached,
                   'total': result.total, 'returned': len(result.items),
                   'sha256': hashlib.sha256(expected.encode()).hexdigest(),
                   'timing': summary, 'reduction_percent': improvement, 'plans': plans}
            report['results'].append(row)
            print(f"{entries:>7} {name:18} cached={cached!s:5} "
                  f"{summary['old']['median_ms']:9.3f} -> {summary['new']['median_ms']:9.3f} ms "
                  f"({improvement:+.1f}%)", flush=True)
    conn.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'data/vocabulary.db')
    parser.add_argument('--baseline', default='7ebdbc0')
    parser.add_argument('--rounds', type=int, default=11)
    parser.add_argument('--scale', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.rounds < 3 or args.scale < 1:
        parser.error('--rounds >= 3 and --scale >= 1 required')
    old = baseline_query(args.baseline)
    report = {'python': sys.version, 'sqlite': sqlite3.sqlite_version,
              'platform': platform.platform(), 'baseline': args.baseline,
              'rounds': args.rounds, 'scale': args.scale,
              'note': 'Warm SQLite page cache; service call only; no HTTP/Redis; sequential alternating versions.'}
    if args.scale == 1:
        report['measurement'] = measure(args.db, old, args.rounds)
    else:
        with tempfile.TemporaryDirectory(prefix='entries-benchmark-') as directory:
            fixture = Path(directory) / 'growth.db'
            growth_fixture(args.db, fixture, args.scale)
            report['measurement'] = measure(fixture, old, args.rounds)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
