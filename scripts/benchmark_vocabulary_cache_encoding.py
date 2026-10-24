"""Isolate current vs bounded cache encoding for standard-word result shapes.

An analysis prototype only: vars is safe for these plain result dataclasses,
not proposed as a general replacement for FastAPI's jsonable_encoder.
"""
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark_vocabulary_entries import readonly
from app.service.vocabulary.query import query_vocabulary_standard_words
from app.service.vocabulary.cache import encoded


def bounded(value, maximum):
    encoder = json.JSONEncoder(default=vars, ensure_ascii=False, sort_keys=True,
                               separators=(',', ':'))
    chunks, size = [], 0
    for chunk in encoder.iterencode(value):
        size += len(chunk.encode('utf-8'))
        if maximum is not None and size > maximum:
            return None
        chunks.append(chunk)
    return ''.join(chunks)


def main():
    conn = readonly(ROOT / 'data/vocabulary.db')
    session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=conn))
    reports = []
    for limit in (100, 1000, 10000, None):
        result = query_vocabulary_standard_words(session=session, limit=limit)
        # Existing permanent 100/1000 keys bypass the 128 KiB cap: preserve it.
        maximum = None if limit in (100, 1000) else 128 * 1024
        expected = encoded(result)
        assert json.loads(expected) == asdict(result)
        candidate = bounded(result, maximum)
        if maximum is not None and len(expected.encode()) > maximum:
            assert candidate is None
        else:
            assert candidate == expected
        samples = {'current': [], 'candidate': []}
        for iteration in range(5):
            order = ['current', 'candidate'] if iteration % 2 == 0 else ['candidate', 'current']
            for version in order:
                start = time.perf_counter()
                value = encoded(result) if version == 'current' else bounded(result, maximum)
                samples[version].append((time.perf_counter() - start) * 1000)
        report = {'limit': limit, 'groups': len(result.standard_words), 'total': result.total,
                  'utf8_bytes': len(expected.encode()), 'cache_cap': maximum,
                  'median_ms': {v: statistics.median(s) for v, s in samples.items()},
                  'samples_ms': samples, 'candidate_skips_store': candidate is None,
                  'scope': 'Cache encoding only, excluding SQL, Redis and HTTP response encoding.'}
        reports.append(report)
        print(json.dumps(report), flush=True)
    conn.close()
    Path(sys.argv[1]).write_text(json.dumps(reports, indent=2) + '\n')


if __name__ == '__main__':
    main()
