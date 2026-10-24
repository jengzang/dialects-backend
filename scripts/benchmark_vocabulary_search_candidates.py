"""Read-only service experiments, NOT changes to production query behavior.

Compare working-tree queries with isolated in-process candidate modules. Full
ordered results must agree. Output contains all timings and query plans.
"""
import argparse
from dataclasses import asdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark_vocabulary_entries import growth_fixture, readonly
from app.service.vocabulary import script_variants

SOURCE = (ROOT / 'app/service/vocabulary/query.py').read_text()


def load(name, source=SOURCE):
    module = ModuleType('_search_experiment_' + name)
    sys.modules[module.__name__] = module
    exec(compile(source, name, 'exec'), module.__dict__)
    return module


def metadata_candidate():
    source = SOURCE
    for field in ('province', 'city'):
        source = source.replace(f'clauses.append("l.{field} = ?")',
            f'clauses.append("(e.user_id, e.location_name) IN " '
            f'"(SELECT p.user_id, p.location_name FROM vocabulary_locations p WHERE p.{field} = ?)")')
    module = load('metadata', source)
    original = module._append_like_group
    def grouped_like(*, clauses, values, columns, terms):
        columns, terms = list(dict.fromkeys(columns)), list(dict.fromkeys(terms))
        entry = [column for column in columns if not column.startswith('l.')]
        location = [column for column in columns if column.startswith('l.')]
        # LEFT JOIN's NULL row COALESCEs to ''. All-% patterns match that row,
        # unlike an identity IN subquery. Preserve original SQL in that case.
        if not location or any(not term.strip('%') for term in terms):
            return original(clauses=clauses, values=values, columns=columns, terms=terms)
        branches, binds = [], []
        if entry:
            original(clauses=branches, values=binds, columns=entry, terms=terms)
        metadata_parts, metadata_binds = [], []
        original(clauses=metadata_parts, values=metadata_binds,
                 columns=[column.replace('l.', 'p.') for column in location], terms=terms)
        branches.append('(e.user_id, e.location_name) IN '
                        '(SELECT p.user_id, p.location_name FROM vocabulary_locations p '
                        'WHERE ' + ' AND '.join(metadata_parts) + ')')
        clauses.append('(' + ' OR '.join(branches) + ')')
        values.extend(binds + metadata_binds)
    module._append_like_group = grouped_like
    return module


def nonnull_candidate():
    module = load('nonnull')
    original = module._append_like_group
    def like(*, clauses, values, columns, terms):
        result = []
        original(clauses=result, values=values, columns=list(dict.fromkeys(columns)),
                 terms=list(dict.fromkeys(terms)))
        for clause in result:
            for field in ('standard_word', 'local_expression', 'ipa', 'location_name'):
                clause = clause.replace(f"COALESCE(e.{field}, '')", f'e.{field}')
            clauses.append(clause)
    module._append_like_group = like
    return module


def scenarios():
    return {
        'default': {},
        'q-common': {'q': '什么'},
        'q-one-char': {'q': '人'},
        'q-traditional': {'q': '太陽'},
        'q-rare': {'q': '不可能命中8f0b7e4d9a'},
        'q-definition': {'q': '什么', 'search_fields': ['definition']},
        'q-pronunciation': {'q': 'a', 'search_fields': ['pronunciation']},
        'q-detail': {'q': '常用', 'search_fields': ['detail']},
        'q-location': {'q': '广州', 'search_fields': ['location']},
        'q-mixed-location': {'q': '廣州', 'search_fields': ['headword', 'location']},
        'province-large': {'province': '廣東'},
        'province-small': {'province': '貴州'},
        'province-city': {'province': '廣東', 'city': '廣州'},
        'locations-text': {'locations': ['廣州', '香港']},
        'q-and-province': {'q': '什么', 'province': '廣東'},
        'region-small': {'regions': ['西北-關隴']},
        'region-large': {'regions': ['嶺南']},
        'regions-multi': {'regions': ['嶺南', '閩']},
        'q-and-region': {'q': '什么', 'regions': ['嶺南']},
        'combined': {'q': '人', 'province': '廣東', 'city': '廣州',
                     'regions': ['嶺南'], 'locations': ['廣州']},
        'wildcard-percent': {'q': '%', 'search_fields': ['location']},
        'wildcard-underscore': {'q': '_', 'search_fields': ['location']},
        'contradictory': {'province': '廣東', 'city': '不可能城市8f0b7e4d9a'},
    }


def check_metadata_edges():
    """Check orphan/NULL/wildcard cases absent or scarce in the real fixture."""
    current, candidate = load('edge_current'), metadata_candidate()
    conn = sqlite3.connect(':memory:')
    with readonly(ROOT / 'data/vocabulary.db') as source:
        for table in ('vocabulary_locations', 'vocabulary_entries'):
            ddl = source.execute('SELECT sql FROM sqlite_master WHERE type=\'table\' AND name=?',
                                 (table,)).fetchone()[0]
            conn.execute(ddl)
    conn.executemany('INSERT INTO vocabulary_locations '
        '(user_id, location_name, coordinates, province, city) VALUES (?,?,?,?,?)', [
        (1, '同名', '106,27', '广东', '广州'),
        (2, '同名', '107,28', '贵州', '贵阳'),
        (3, '', '', None, None),
    ])
    conn.executemany('INSERT INTO vocabulary_entries '
        '(user_id, location_name, standard_word, local_expression, ipa, notes, informations) '
        'VALUES (?,?,?,?,?,?,?)', [
        (1, '同名', '太阳', '广州', 'a', None, None),
        (2, '同名', '太陽', '日頭', 'b', '', ''),
        (3, '', '月亮', '', '', None, None),
        (4, '孤立地点', '月亮', '月光', 'a', '', ''),
    ])
    session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=conn))
    cases = [
        {}, {'province': '广东'}, {'province': '广东', 'city': '贵阳'},
        {'q': '广州', 'search_fields': ['headword', 'location']},
        {'q': '%', 'search_fields': ['location']},
        {'q': '%%', 'search_fields': ['detail', 'location']},
        {'q': '_', 'search_fields': ['location']},
        {'locations': ['%']}, {'locations': ['孤立']},
        {'q': '%', 'province': '广东', 'search_fields': ['location']},
        {'q': '日', 'locations': ['同名']},
    ]
    count = 0
    for endpoint in ('items', 'standard_words', 'map_points'):
        for options in cases:
            old = getattr(current, 'query_vocabulary_' + endpoint)(session=session, **options)
            new = getattr(candidate, 'query_vocabulary_' + endpoint)(session=session, **options)
            assert asdict(old) == asdict(new), ('metadata edge', endpoint, options)
            count += 1
    conn.close()
    return count


def run(path, rounds, experiment):
    current = load('current')
    if experiment == 'metadata':
        candidate = metadata_candidate()
    elif experiment == 'nonnull':
        candidate = nonnull_candidate()
    elif experiment == 'word-cache':
        candidate = load('word_cache')
        candidate.standard_word_key = lru_cache(maxsize=65536)(
            lambda value: script_variants._T2S.convert(value.strip()) if value.strip() else '')
    elif experiment == 'standard-auto-index':
        candidate = load('auto_index', SOURCE.replace(
            'vocabulary_entries e INDEXED BY idx_vocabulary_entries_user_location ',
            'vocabulary_entries e '))
    elif experiment == 'standard-table-scan':
        source = SOURCE.replace("'vocabulary_entries e INDEXED BY idx_vocabulary_entries_user_location '",
                                "'vocabulary_entries e NOT INDEXED '")
        source = source.replace("if regions else 'vocabulary_entries e '",
                                "if regions else 'vocabulary_entries e NOT INDEXED '")
        candidate = load('standard_table_scan', source)
    elif experiment == 'word-bitmap':
        source = SOURCE.replace('grouped: dict[str, list] = {}',
                                'grouped: dict[str, list] = {}\n    location_bits = {}')
        source = source.replace('group = grouped[key] = [0, set(), {}]',
                                'group = grouped[key] = [0, 0, {}]')
        source = source.replace('group[1].add(location_name)',
                                'group[1] |= location_bits.setdefault(location_name, 1 << len(location_bits))')
        source = source.replace('len(locations)', 'locations.bit_count()')
        candidate = load('bitmap', source)
    else:
        raise ValueError(experiment)
    conn = readonly(path)
    session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=conn))
    reports = []
    endpoints = ['standard_words'] if experiment in {'word-cache', 'standard-auto-index', 'standard-table-scan', 'word-bitmap'} else ['items', 'standard_words', 'map_points']
    selected = scenarios()
    if experiment in {'word-cache', 'word-bitmap'}:
        selected = {k: selected[k] for k in ('default', 'province-large', 'region-large', 'q-common')}
        selected['full-standard-words'] = {'limit': None}
    elif experiment == 'standard-auto-index':
        selected = {k: v for k, v in selected.items() if 'regions' in v}
    elif experiment in {'nonnull', 'standard-table-scan'}:
        selected = {k: v for k, v in selected.items() if 'q' in v or 'locations' in v}
    else:
        selected = {k: v for k, v in selected.items() if 'province' in v or 'city' in v
                    or 'locations' in v or 'location' in v.get('search_fields', [])}
    for endpoint in endpoints:
        for name, options in selected.items():
            functions = {version: getattr(module, 'query_vocabulary_' + endpoint)
                         for version, module in [('current', current), ('candidate', candidate)]}
            payloads, plans = {}, {}
            cold = {}
            for version, function in functions.items():
                statements = []
                conn.set_trace_callback(statements.append)
                start = time.perf_counter()
                result = function(session=session, **options)
                cold[version] = (time.perf_counter() - start) * 1000
                conn.set_trace_callback(None)
                payloads[version] = json.dumps(asdict(result), ensure_ascii=False, sort_keys=True)
                plans[version] = [{'sql': sql, 'plan': conn.execute('EXPLAIN QUERY PLAN ' + sql).fetchall()}
                                  for sql in statements if sql.startswith('SELECT')]
            assert payloads['current'] == payloads['candidate'], (experiment, endpoint, name)
            samples = {'current': [], 'candidate': []}
            for iteration in range(rounds):
                order = ['current', 'candidate'] if iteration % 2 == 0 else ['candidate', 'current']
                for version in order:
                    start = time.perf_counter()
                    result = functions[version](session=session, **options)
                    samples[version].append((time.perf_counter() - start) * 1000)
                    assert json.dumps(asdict(result), ensure_ascii=False, sort_keys=True) == payloads['current']
            medians = {v: statistics.median(s) for v, s in samples.items()}
            improvement = (1 - medians['candidate'] / medians['current']) * 100
            summary = {'endpoint': endpoint, 'scenario': name, 'options': options,
                       'median_ms': medians, 'samples_ms': samples, 'initial_ms': cold,
                       'reduction_percent': improvement, 'plans': plans,
                       'total': getattr(result, 'total', getattr(result, 'total_entries', None)),
                       'sha256': hashlib.sha256(payloads['current'].encode()).hexdigest()}
            if endpoint == 'standard_words':
                summary['conversion_cache'] = {v: getattr(m.standard_word_key, 'cache_info')()._asdict()
                                                for v, m in [('current', current), ('candidate', candidate)]}
            reports.append(summary)
            print(f'{experiment:19} {endpoint:14} {name:23} '
                  f'{medians["current"]:9.3f} -> {medians["candidate"]:9.3f} ms '
                  f'({improvement:+.1f}%)', flush=True)
    conn.close()
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', choices=['metadata', 'nonnull', 'word-cache', 'standard-auto-index', 'standard-table-scan', 'word-bitmap'], required=True)
    parser.add_argument('--scale', type=int, default=1)
    parser.add_argument('--rounds', type=int, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.rounds < 3 or args.scale < 1:
        parser.error('rounds >= 3, scale >= 1 required')
    source = ROOT / 'data/vocabulary.db'
    report = {'experiment': args.experiment, 'scale': args.scale, 'rounds': args.rounds,
              'python': sys.version, 'sqlite': sqlite3.sqlite_version, 'platform': platform.platform(),
              'scope': 'Warm in-process service only; Redis and HTTP excluded; current is working-tree query.'}
    if args.experiment == 'metadata':
        report['edge_cases_checked'] = check_metadata_edges()
    if args.scale == 1:
        report['results'] = run(source, args.rounds, args.experiment)
    else:
        with tempfile.TemporaryDirectory(prefix='search-analysis-') as directory:
            target = Path(directory) / 'growth.db'
            growth_fixture(source, target, args.scale)
            report['results'] = run(target, args.rounds, args.experiment)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
