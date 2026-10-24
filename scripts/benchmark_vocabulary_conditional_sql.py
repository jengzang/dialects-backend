"""Measure actual working-tree queries against a saved before-change query.py."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark_vocabulary_entries import growth_fixture, readonly
from scripts.benchmark_vocabulary_search_candidates import load, scenarios


def run(path, baseline, rounds):
    old, new = load('before_conditional', baseline), load('actual_conditional')
    conn = readonly(path)
    session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=conn))
    results = []
    for endpoint in ('items', 'standard_words', 'map_points'):
        cases = scenarios()
        cases['q-wildcard-default'] = {'q': '%'}
        cases['q-and-locations'] = {'q': '什么', 'locations': ['廣州']}
        if endpoint == 'standard_words':
            cases['full-result'] = {'limit': None}
            cases['q-full-result'] = {'q': '人', 'limit': None}
        elif endpoint == 'items':
            cases['exact-word-location'] = {'standard_words': ['太阳'], 'locations': ['廣州']}
            cases['exact-word-province'] = {'standard_words': ['太阳'], 'province': '廣東'}
            cases['location-deep'] = {'locations': ['廣州'], 'page': 100}
        for name, params in cases.items():
            functions = {v: getattr(m, 'query_vocabulary_' + endpoint)
                         for v, m in [('old', old), ('new', new)]}
            expected, plans = None, {}
            for version, function in functions.items():
                statements = []
                conn.set_trace_callback(statements.append)
                value = function(session=session, **params)
                conn.set_trace_callback(None)
                payload = json.dumps(asdict(value), ensure_ascii=False, sort_keys=True)
                if expected is None:
                    expected = payload
                assert payload == expected, (endpoint, name, version)
                plans[version] = [{'sql': sql, 'plan': conn.execute('EXPLAIN QUERY PLAN ' + sql).fetchall()}
                                  for sql in statements if sql.startswith('SELECT')]
            samples = {'old': [], 'new': []}
            for iteration in range(rounds):
                order = ['old', 'new'] if iteration % 2 == 0 else ['new', 'old']
                for version in order:
                    start = time.perf_counter()
                    value = functions[version](session=session, **params)
                    samples[version].append((time.perf_counter() - start) * 1000)
                    assert json.dumps(asdict(value), ensure_ascii=False, sort_keys=True) == expected
            medians = {v: statistics.median(t) for v, t in samples.items()}
            reduction = (1 - medians['new'] / medians['old']) * 100
            results.append({'endpoint': endpoint, 'scenario': name, 'params': params,
                            'median_ms': medians, 'samples_ms': samples, 'plans': plans,
                            'total': getattr(value, 'total', getattr(value, 'total_entries', None)),
                            'sha256': hashlib.sha256(expected.encode()).hexdigest(),
                            'reduction_percent': reduction})
            print(f'{endpoint:14} {name:24} {medians["old"]:9.3f} -> '
                  f'{medians["new"]:9.3f} ms ({reduction:+.1f}%)', flush=True)
    conn.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scale', type=int, default=1)
    parser.add_argument('--rounds', type=int, default=5)
    args = parser.parse_args()
    if args.scale < 1 or args.rounds < 3:
        parser.error('scale >= 1 and rounds >= 3 required')
    baseline = args.baseline.read_text()
    report = {'scale': args.scale, 'rounds': args.rounds, 'python': sys.version,
              'platform': platform.platform(), 'baseline_sha256': hashlib.sha256(baseline.encode()).hexdigest(),
              'note': 'Warm SQLite pages; service only, no Redis/HTTP; no response cache.'}
    source = ROOT / 'data/vocabulary.db'
    if args.scale == 1:
        report['results'] = run(source, baseline, args.rounds)
    else:
        with tempfile.TemporaryDirectory(prefix='conditional-sql-benchmark-') as directory:
            target = Path(directory) / 'growth.db'
            growth_fixture(source, target, args.scale)
            report['results'] = run(target, baseline, args.rounds)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
