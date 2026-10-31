"""Compare exact count SQL inside a 2 CPU / 2 GiB Linux container.

Stdlib only. Run with /source mounted read-only and /work as writable workdir:
docker run --rm --cpus 2 --memory 2g --memory-swap 2g \
  -v "$PWD:/source:ro" -w /work python:3.12-slim \
  python /source/scripts/benchmark_vocabulary_location_count.py

Copies source DB; never alters repository data. Measures SQL, not HTTP latency.
"""
import ast
import hashlib
import json
import platform
import resource
import shutil
import sqlite3
import statistics
import time
from pathlib import Path
from typing import Iterable


def main():
    limits = {name: Path('/sys/fs/cgroup', name).read_text().strip()
              for name in ('cpu.max', 'memory.max', 'memory.swap.max')}
    assert limits == {'cpu.max': '200000 100000', 'memory.max': '2147483648',
                      'memory.swap.max': '0'}, limits
    source = Path('/source/app/service/vocabulary/query.py').read_text()
    # Load the actual pure SQL builder without installing unrelated app dependencies.
    tree = ast.parse(source)
    nodes = [node for node in tree.body if
             isinstance(node, ast.FunctionDef) and node.name in
             {'_append_like_group', '_location_first_count_sql', '_build_filter_clause',
              '_normalize_multi_value', '_normalize_search_fields', '_append_search_like_group'} or
             isinstance(node, ast.Assign) and any(
                 isinstance(t, ast.Name) and t.id in {'SEARCH_FIELD_COLUMNS', 'DEFAULT_SEARCH_FIELDS'}
                 for t in node.targets)]
    ns = {'Iterable': Iterable, 'partition_filter': lambda *args, **kw: ('', [])}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'query.py', 'exec'), ns)

    current, growth = Path('/work/current.db'), Path('/work/growth.db')
    # Fixture is an offline database. Refuse a live WAL database rather than
    # copying an inconsistent snapshot from the read-only mount.
    wal = Path('/source/data/vocabulary.db-wal')
    assert not wal.exists() or wal.stat().st_size == 0
    shutil.copyfile('/source/data/vocabulary.db', current)
    with sqlite3.connect(current) as src, sqlite3.connect(growth) as dst:
        src.backup(dst)
        dst.execute('ATTACH DATABASE ? AS original', (str(current),))
        stride = dst.execute('SELECT MAX(user_id)+1 FROM (SELECT user_id FROM '
                             'vocabulary_entries UNION ALL SELECT user_id FROM vocabulary_locations)').fetchone()[0]
        for copy in range(1, 10):
            for table in ('vocabulary_locations', 'vocabulary_entries'):
                columns = [r[1] for r in dst.execute(f'PRAGMA table_info({table})') if r[1] != 'id']
                names = ','.join('"' + c + '"' for c in columns)
                expressions = ','.join('user_id+?' if c == 'user_id' else '"' + c + '"' for c in columns)
                dst.execute(f'INSERT INTO {table} ({names}) SELECT {expressions} FROM original.{table}', (copy*stride,))
        dst.execute('ANALYZE')

    results = []
    cases = [['廣州'], ['貴州'], ['香港'], ['廣州', '香港'], ['不存在'],
             ['廣州', '廣'], ['廣州', '孤立'], ['廣%'], ['_'], ['%']]

    def measure(conn, label, terms):
        where, values = ns['_build_filter_clause'](q=None, search_fields=None, locations=terms)
        join = ('LEFT JOIN vocabulary_locations l ON l.user_id=e.user_id '
                'AND l.location_name=e.location_name ') if 'l.' in where else ''
        original = 'SELECT COUNT(*) FROM vocabulary_entries e ' + join + 'WHERE ' + where
        old = original, values
        new = ns['_location_first_count_sql'](terms, *old)
        samples = {'old': [], 'new': []}
        totals = {}
        for round_no in range(11):
            pairs = [('old', old), ('new', new)]
            if round_no % 2:
                pairs.reverse()
            for kind, (sql, params) in pairs:
                start = time.perf_counter()
                totals[kind] = conn.execute(sql, params).fetchone()[0]
                elapsed = (time.perf_counter() - start) * 1000
                if round_no >= 2:
                    samples[kind].append(elapsed)
            assert totals['old'] == totals['new'], (label, terms, totals)
        result = dict(dataset=label, terms=terms, total=totals['new'],
                      old_ms=statistics.median(samples['old']),
                      new_ms=statistics.median(samples['new']), samples=samples)
        results.append(result)
        print(json.dumps({k: v for k, v in result.items() if k != 'samples'}, ensure_ascii=False), flush=True)

    for path in (current, growth):
        with sqlite3.connect(path) as conn:
            for terms in cases:
                measure(conn, path.stem, terms)

    # Cardinality boundary and many unique names: fallback must remain exact.
    with sqlite3.connect('/work/cardinality.db') as conn:
        conn.executescript('CREATE TABLE vocabulary_entries(user_id INTEGER NOT NULL, '
            'location_name TEXT NOT NULL); CREATE INDEX entries_name ON vocabulary_entries(location_name); '
            'CREATE INDEX entries_identity ON vocabulary_entries(user_id,location_name); '
            'CREATE TABLE vocabulary_locations(user_id INTEGER NOT NULL, location_name TEXT NOT NULL, '
            'UNIQUE(user_id,location_name));')
        for col in ('province', 'city', 'county', 'town', 'administrative_village',
                    'natural_village', 'yindian_region', 'atlas_region'):
            conn.execute(f'ALTER TABLE vocabulary_locations ADD COLUMN {col} TEXT')
        for names, repeats in ((256, 1000), (257, 1000), (10000, 1)):
            conn.execute('DELETE FROM vocabulary_entries')
            conn.executemany('INSERT INTO vocabulary_entries VALUES (?,?)',
                ((1, f'地点{i:06}') for i in range(names) for _ in range(repeats)))
            conn.commit()
            for terms in (['地点000001'], ['不存在'], ['地点']):
                measure(conn, f'{names}names_x{repeats}', terms)
    report = dict(limits=limits, platform=platform.platform(), sqlite=sqlite3.sqlite_version,
                  source_sha256=hashlib.sha256(source.encode()).hexdigest(), results=results,
                  maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  memory_events=Path('/sys/fs/cgroup/memory.events').read_text(),
                  cpu_stat=Path('/sys/fs/cgroup/cpu.stat').read_text())
    Path('/work/results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
