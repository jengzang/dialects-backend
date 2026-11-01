"""Stdlib-only replay of frozen SQL; intended for a local constrained container.

All DB writes are confined to the explicitly requested growth fixture. Input
database is opened read-only. No application imports, network or server access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sqlite3
import statistics
import time


def cold_page_first(conn, job):
    rows = conn.execute(job['sql'][1]).fetchall()
    total = (len(rows) if len(rows) < 50 else conn.execute(job['sql'][0]).fetchone()[0])
    return total, rows


def digest(conn, job, full_entries=False):
    h = hashlib.sha256()
    statements = job['sql']
    if job.get('flow') == 'cold_page_first':
        total, _ = cold_page_first(conn, job)
        h.update(repr((total,)).encode())
        statements = statements[1:]
    for sql in statements:
        if full_entries:
            import re
            sql = re.sub(r'LIMIT \d+ OFFSET \d+', 'LIMIT -1 OFFSET 0', sql)
        for row in conn.execute(sql):
            h.update(repr(row).encode())
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--jobs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scale', type=int, default=1)
    parser.add_argument('--rounds', type=int, default=3)
    args = parser.parse_args()
    src = sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True)
    if args.scale > 1:
        target = args.output.with_suffix('.sqlite')
        assert not target.exists(), target
        with sqlite3.connect(target) as dest:
            src.backup(dest)
            dest.execute('ATTACH DATABASE ? AS original', (args.db.resolve().as_uri() + '?mode=ro',))
            stride = dest.execute('SELECT MAX(user_id)+1 FROM (SELECT user_id FROM '
                    'original.vocabulary_entries UNION ALL SELECT user_id FROM original.vocabulary_locations)').fetchone()[0]
            for copy in range(1, args.scale):
                for table in ('vocabulary_entries', 'vocabulary_locations'):
                    columns = [r[1] for r in dest.execute(f'PRAGMA table_info({table})') if r[1] != 'id']
                    names = ','.join('"' + c + '"' for c in columns)
                    expr = ','.join('user_id + ?' if c == 'user_id' else '"' + c + '"' for c in columns)
                    dest.execute(f'INSERT INTO {table} ({names}) SELECT {expr} FROM original.{table}', (copy*stride,))
        src.close()
        src = sqlite3.connect(target.resolve().as_uri() + '?mode=ro', uri=True)
    results, references = [], {}
    jobs = json.loads(args.jobs.read_text())
    # Interleave candidate order on alternate rounds to reduce warm-cache bias.
    timings = [[] for _ in jobs]
    for round_no in range(args.rounds):
        for i in (range(len(jobs)) if round_no % 2 == 0 else reversed(range(len(jobs)))):
            job = jobs[i]
            start = time.perf_counter()
            if job.get('flow') == 'cold_page_first':
                cold_page_first(src, job)
            else:
                for sql in job['sql']:
                    src.execute(sql).fetchall()
            timings[i].append((time.perf_counter() - start)*1000)
    for i, job in enumerate(jobs):
        key = (job['endpoint'], job['name'])
        signature = digest(src, job, full_entries=job['endpoint'] == 'items')
        if job['candidate'] == 'current':
            references[key] = signature
        assert signature == references[key], (key, job['candidate'])
        results.append(dict(job, median_ms=statistics.median(timings[i]), samples_ms=timings[i],
                            digest=signature, plans=[src.execute('EXPLAIN QUERY PLAN '+sql).fetchall() for sql in job['sql']]))
    metadata = {'entries': src.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0],
                'sqlite': sqlite3.sqlite_version, 'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'limits': {p: Path('/sys/fs/cgroup/'+p).read_text().strip() for p in
                           ('cpu.max','memory.max','memory.swap.max') if Path('/sys/fs/cgroup/'+p).exists()},
                'results': results}
    args.output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(json.dumps({k:v for k,v in metadata.items() if k != 'results'}))


if __name__ == '__main__':
    main()
