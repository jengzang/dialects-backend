"""Measure bounded conversion cache allocation and sequential reuse, not HTTP."""
import argparse
from functools import lru_cache
import gc
import json
from pathlib import Path
import sqlite3
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.service.vocabulary.script_variants import _T2S


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size', type=int, required=True)
    parser.add_argument('--word-scale', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    conn = sqlite3.connect((ROOT / 'data/vocabulary.db').as_uri() + '?mode=ro', uri=True)
    convert = lru_cache(maxsize=args.size)(lambda value: _T2S.convert(value.strip()))
    def visit():
        count = 0
        for copy in range(args.word_scale):
            for (word,) in conn.execute('SELECT DISTINCT standard_word FROM vocabulary_entries '
                                         "WHERE standard_word <> '' ORDER BY standard_word"):
                convert(word if copy == 0 else word + '#' + str(copy))
                count += 1
        return count
    tracemalloc.start()
    words = visit()
    gc.collect()
    retained, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    before = convert.cache_info()
    start = time.perf_counter()
    visit()
    elapsed = time.perf_counter() - start
    after = convert.cache_info()
    report = {'size': args.size, 'word_scale': args.word_scale, 'distinct_spellings': words,
              'cache_python_retained_mib': retained / 1024**2,
              'traced_peak_mib': peak / 1024**2,
              'second_pass_seconds': elapsed, 'second_pass_hits': after.hits - before.hits,
              'second_pass_misses': after.misses - before.misses,
              'cache_items': after.currsize,
              'scope': 'Python traced retained allocations during cache fill, not process RSS; '
                       'second pass includes SQL iteration and conversion only, not aggregation.'}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)
    conn.close()


if __name__ == '__main__':
    main()
