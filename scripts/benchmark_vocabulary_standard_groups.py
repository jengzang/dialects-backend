"""Local prototype only: promote single-value groups to sets/dicts on demand.

Measures Python allocations separately from elapsed time. tracemalloc excludes
native SQLite/OpenCC memory; this is not a production memory prediction.
"""
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import subprocess
import time
import tracemalloc
from types import SimpleNamespace

from scripts.benchmark_vocabulary_search_candidates import load
from scripts.benchmark_vocabulary_entries import readonly

SOURCE = subprocess.check_output(['git', 'show', '29ebfa0:app/service/vocabulary/query.py'],
                                 cwd=Path(__file__).resolve().parents[1], text=True)


def compact():
    source = SOURCE.replace('grouped[key] = [0, set(), {}]', 'grouped[key] = [0, None, word]')
    old = '''        if location_name:
            group[1].add(location_name)
        variant_counts = group[2]
        variant_counts[word] = variant_counts.get(word, 0) + entry_count
'''
    new = '''        if location_name:
            if group[1] is None:
                group[1] = location_name
            elif isinstance(group[1], str):
                if group[1] != location_name:
                    group[1] = {group[1], location_name}
            else:
                group[1].add(location_name)
        if isinstance(group[2], str):
            if group[2] != word:
                group[2] = {group[2]: group[0] - entry_count, word: entry_count}
        else:
            group[2][word] = group[2].get(word, 0) + entry_count
'''
    assert old in source
    source = source.replace(old, new)
    old = '''        representative = min(
            variant_counts,
            key=lambda variant: (-variant_counts[variant], variant),
        )'''
    new = '''        representative = (variant_counts if isinstance(variant_counts, str) else min(
            variant_counts, key=lambda variant: (-variant_counts[variant], variant)))'''
    assert old in source
    source = source.replace(old, new)
    source = source.replace('return (-len(locations), -entry_count, representative)',
                            'return (-(1 if isinstance(locations, str) else len(locations or ())), -entry_count, representative)')
    old = '''        variants = sorted(
            variant_counts,
            key=lambda variant: (-variant_counts[variant], variant),
        )'''
    new = '''        variants = ([variant_counts] if isinstance(variant_counts, str) else sorted(
            variant_counts, key=lambda variant: (-variant_counts[variant], variant)))'''
    assert old in source
    source = source.replace(old, new)
    source = source.replace('location_count=len(locations),',
                            'location_count=1 if isinstance(locations, str) else len(locations or ()),')
    return load('compact_groups', source)


def main():
    modules = {'current': load('groups_current', SOURCE), 'compact': compact()}
    output = []
    with readonly(Path('data/vocabulary.db')) as conn:
        session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=conn))
        for options in ({'limit': 1000}, {'limit': None}, {'q': '皮', 'limit': None},
                        {'q': '太陽', 'limit': None}, {'locations': ['香港'], 'limit': None}):
            results = {k: asdict(m.query_vocabulary_standard_words(session=session, **options))
                       for k, m in modules.items()}
            assert results['current'] == results['compact'], options
            timings = {k: [] for k in modules}
            for round_no in range(9):
                for k in (list(modules) if round_no % 2 == 0 else reversed(list(modules))):
                    start = time.perf_counter()
                    result = modules[k].query_vocabulary_standard_words(session=session, **options)
                    elapsed = (time.perf_counter() - start) * 1000
                    del result
                    timings[k].append(elapsed)
            allocations = {}
            for k, module in modules.items():
                tracemalloc.start()
                result = module.query_vocabulary_standard_words(session=session, **options)
                allocations[k] = tracemalloc.get_traced_memory()[1]
                tracemalloc.stop()
                del result
            output.append(dict(options=options, groups=results['current']['total'],
                               samples_ms=timings, median_ms={k: statistics.median(v) for k,v in timings.items()},
                               python_peak_bytes=allocations))
    path = Path('outputs/vocabulary-local-20261101/standard-groups.json')
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(path.read_text())


if __name__ == '__main__':
    main()
