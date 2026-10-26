"""Measure one read-only query in a fresh process; run timing separately.

RSS includes imports/SQLite/result. tracemalloc is Python-only, not total memory.
Use separate processes with --version before/after for meaningful peak comparison.
"""
import argparse
import json
from pathlib import Path
import resource
import subprocess
import sys
import tracemalloc
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark_vocabulary_entries import readonly
from scripts.benchmark_vocabulary_search_candidates import load


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, default=ROOT / 'data/vocabulary.db')
    p.add_argument('--baseline', default='20bf8f8')
    p.add_argument('--version', choices=['before', 'after'], required=True)
    p.add_argument('--endpoint', choices=['items', 'standard_words'], required=True)
    p.add_argument('--q', default='什么')
    p.add_argument('--locations', nargs='+', default=['廣州'])
    p.add_argument('--trace', action='store_true')
    args = p.parse_args()
    if args.version == 'before':
        source = subprocess.check_output(['git', 'show', f'{args.baseline}:app/service/vocabulary/query.py'], cwd=ROOT, text=True)
        module = load('resource_before', source)
    else:
        module = load('resource_after')
    conn = readonly(args.db)
    session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=conn))
    params = dict(q=args.q, locations=args.locations)
    if args.endpoint == 'standard_words':
        params['limit'] = None
    if args.trace:
        tracemalloc.start()
    usage_before = resource.getrusage(resource.RUSAGE_SELF)
    result = getattr(module, 'query_vocabulary_' + args.endpoint)(session=session, **params)
    usage_after = resource.getrusage(resource.RUSAGE_SELF)
    python_peak = tracemalloc.get_traced_memory()[1] / 1024 ** 2 if args.trace else None
    if args.trace:
        tracemalloc.stop()
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != 'darwin':
        rss *= 1024
    print(json.dumps(dict(version=args.version, endpoint=args.endpoint, params=params,
                         total=result.total, returned=len(result.items if args.endpoint == 'items' else result.standard_words),
                         process_peak_rss_mib=rss / 1024 ** 2, python_query_peak_mib=python_peak,
                         query_user_cpu_s=usage_after.ru_utime-usage_before.ru_utime,
                         query_system_cpu_s=usage_after.ru_stime-usage_before.ru_stime,
                         input_blocks_delta=usage_after.ru_inblock-usage_before.ru_inblock,
                         output_blocks_delta=usage_after.ru_oublock-usage_before.ru_oublock,
                         note='No Redis/HTTP; RSS process lifetime peak; Python allocation measurement changes CPU cost.')))
    conn.close()


if __name__ == '__main__':
    main()
