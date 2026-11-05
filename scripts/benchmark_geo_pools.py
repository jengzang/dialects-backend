"""Sequential local, read-only before/after benchmark; never starts Redis/HTTP.

Each invocation is a fresh child process. --baseline-ref must identify the code
before this refactor. Legacy source is read from Git; databases are not copied.
"""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['_RUN_TYPE'] = 'MINE'


def rss_mib():
    if sys.platform.startswith('linux'):
        rss = next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines()
                   if line.startswith('VmRSS:'))
    else:
        rss = subprocess.check_output(['ps', '-o', 'rss=', '-p', str(os.getpid())], text=True).strip()
    return int(rss) / 1024


def old_module(ref, path, package):
    source = subprocess.check_output(['git', 'show', f'{ref}:{path}'], text=True)
    module = types.ModuleType(package + '._benchmark_baseline')
    module.__package__ = package
    exec(compile(source, path, 'exec'), module.__dict__)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--service', choices=['toponyms', 'gis'], required=True)
    parser.add_argument('--implementation', choices=['legacy', 'shared'], required=True)
    parser.add_argument('--baseline-ref', default='b299cc2')
    parser.add_argument('--cache-kib', type=int, choices=[2000, 4096], help='shared profile experiment only')
    parser.add_argument('--runs', type=int, choices=range(3, 11), default=5)
    args = parser.parse_args()
    from app.sql.db_pool import get_readonly_db_pool, close_all_pools
    if args.cache_kib is not None:
        if args.implementation != 'shared':
            parser.error('--cache-kib is only valid with --implementation shared')
        from app.sql import db_pool
        db_pool.READONLY_PROFILES = dict(db_pool.READONLY_PROFILES)
        db_pool.READONLY_PROFILES[args.service] = db_pool.READONLY_PROFILES[args.service]._replace(cache_kib=args.cache_kib)
    from app.service.toponyms import repository, resources, streaming
    from app.geo_query import engine as current_engine
    # Match imports before measuring; no connections/geometry caches yet.
    old_resources = old_module(args.baseline_ref, 'app/service/toponyms/resources.py', 'app.service.toponyms')
    old_stream = old_module(args.baseline_ref, 'app/service/toponyms/streaming.py', 'app.service.toponyms')
    old_engine = old_module(args.baseline_ref, 'app/geo_query/engine.py', 'app.geo_query')
    gc.collect()
    rss_before = rss_mib()
    connect = __import__('sqlite3').connect
    opened = 0
    def counted_connect(*values, **kwargs):
        nonlocal opened
        opened += 1
        return connect(*values, **kwargs)
    __import__('sqlite3').connect = counted_connect
    results = []
    if args.service == 'toponyms':
        path = (args.data_dir / 'toponyms.db').resolve(strict=True)
        repository.TOPONYMS_DB_PATH = str(path)
        repository.connection = old_resources.connection if args.implementation == 'legacy' else resources.connection
        reader_class = old_stream.QueryStream if args.implementation == 'legacy' else streaming.QueryStream
        def stream():
            reader = reader_class(str(path), 'names', {'query': '村', 'match_mode': 'contains', 'limit': 5000})
            digest = hashlib.sha256()
            try:
                digest.update(reader.start())
                while not reader.done:
                    digest.update(reader.read())
                return digest.hexdigest()
            finally:
                reader.close()
        workloads = [
            ('names_prefix', {'query': '大', 'match_mode': 'prefix', 'limit': 20},
             lambda: repository.sample_names(query='大', match_mode='prefix', limit=20)),
            ('names_contains', {'query': '村', 'match_mode': 'contains', 'limit': 20},
             lambda: repository.sample_names(query='村', match_mode='contains', limit=20)),
            ('search_exact', {'query': '大村', 'match_mode': 'exact', 'limit': 100},
             lambda: repository.search_toponyms(query='大村', match_mode='exact', limit=100)),
            ('points_prefix', {'query': '大', 'match_mode': 'prefix', 'limit': 5000},
             lambda: repository.list_points_by_name(query='大', match_mode='prefix', limit=5000)),
            ('divisions', {'parent_code': '44'},
             lambda: repository.list_child_divisions(parent_code='44')),
            ('stream_5000', {'query': '村', 'match_mode': 'contains', 'limit': 5000}, stream),
        ]
        engine = None
    else:
        path = (args.data_dir / 'dependency/gis.db').resolve(strict=True)
        cls = old_engine.AreaCityQueryPy if args.implementation == 'legacy' else current_engine.AreaCityQueryPy
        started = time.perf_counter()
        engine = cls()
        engine.init_store(path)
        results.append({'case': 'initialize', 'ms': [(time.perf_counter() - started) * 1000]})
        workloads = [
            ('point', {'lng': 116.4074, 'lat': 39.9042}, lambda: engine.query_point(116.4074, 39.9042).result),
            ('boundary', {'feature_id': 110101}, lambda: engine.read_boundary_by_id(110101)),
            ('search', {'q': '北京'}, lambda: engine.search('北京')),
            ('children', {'parent_id': 11}, lambda: engine.children(parent_id=11)),
        ]
    for name, params, operation in workloads:
        elapsed, cpu, hashes, errors = [], [], [], []
        for _ in range(args.runs):
            started, cpu_start = time.perf_counter(), time.process_time()
            try:
                value = operation()
                elapsed.append((time.perf_counter() - started) * 1000)
                cpu.append((time.process_time() - cpu_start) * 1000)
                hashes.append(hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                                       default=str).encode()).hexdigest())
                del value
            except Exception as exc:
                elapsed.append((time.perf_counter() - started) * 1000)
                cpu.append((time.process_time() - cpu_start) * 1000)
                errors.append(type(exc).__name__ + ': ' + str(exc))
        results.append({'case': name, 'params': params, 'ms': elapsed, 'cpu_ms': cpu,
                        'median_ms': statistics.median(elapsed), 'hashes': hashes, 'errors': errors})
    gc.collect()
    if args.implementation == 'shared':
        live = get_readonly_db_pool(path, args.service)._created_count
    elif engine is not None:
        live = engine._pool._pool.qsize()
    else:
        live = 0
    print(json.dumps({'service': args.service, 'implementation': args.implementation,
                      'runs': args.runs, 'cache_kib_override': args.cache_kib, 'opened_connections': opened, 'idle_connections': live,
                      'rss_baseline_mib': rss_before, 'rss_idle_delta_mib': rss_mib() - rss_before,
                      'results': results}, ensure_ascii=False))
    close_all_pools()
    if engine is not None and args.implementation == 'legacy':
        while not engine._pool._pool.empty():
            engine._pool._pool.get_nowait().close()


if __name__ == '__main__':
    main()
