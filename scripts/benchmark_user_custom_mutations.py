"""Local-only HTTP/SQLite benchmark. Always uses a new disposable database.

The legacy baseline deliberately models the former two-commit delete/recreate
flow, not the current compatibility adapter. This is not a production load test.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import platform
import resource
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

from app.common.time_utils import now_utc_naive
from app.schemas.user.custom_mutations import BatchUpdateRequest
from app.service.user.core.models import Base, Information
from app.service.user.submission.mutations import batch_update

FIELDS = dict(簡稱='甲', 音典分區='乙', 經緯度='113,23', 聲韻調='', 特徵='阴平', 值='55', 說明='')


def percentile(values, fraction):
    values = sorted(values)
    return round(values[min(len(values) - 1, int((len(values) - 1) * fraction))], 3) if values else None


def run_case(directory, rows, concurrency, iterations, mode):
    engine = create_engine(f'sqlite:///{directory}/{mode}.db', connect_args={'check_same_thread': False, 'timeout': 5})

    @event.listens_for(engine, 'connect')
    def configure(conn, _):
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=5000')
        conn.execute('PRAGMA cache_size=-2000')

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([Information(**FIELDS, user_id=7, username='bench', maxValue='55', created_at=now_utc_naive()) for _ in range(rows * concurrency)])
        db.commit()
    sql_count = 0
    writer_waits = []
    count_lock = threading.Lock()

    @event.listens_for(engine, 'before_cursor_execute')
    def count_sql(conn, cursor, statement, parameters, context, executemany):
        nonlocal sql_count
        with count_lock:
            sql_count += 1
        if statement.upper().startswith('BEGIN IMMEDIATE'):
            context.custom_writer_started = time.perf_counter()

    @event.listens_for(engine, 'after_cursor_execute')
    def count_wait(conn, cursor, statement, parameters, context, executemany):
        if hasattr(context, 'custom_writer_started'):
            writer_waits.append((time.perf_counter() - context.custom_writer_started) * 1000)

    app = FastAPI()
    user = SimpleNamespace(id=7, username='bench', role='user')

    @app.get('/probe')
    def probe():
        with factory() as db:
            return {'value': db.scalar(select(Information.值).limit(1))}

    @app.post('/update/{worker}')
    def update(worker: int):
        low = worker * rows + 1
        with factory() as db:
            records = db.scalars(select(Information).where(Information.id >= low, Information.id < low + rows)).all()
            items = [dict(**FIELDS, id=row.id, version=row.version) for row in records]
        if mode == 'atomic':
            return batch_update(user, BatchUpdateRequest(items=items), factory)
        # Model old delete/recreate: two independently committed writes.
        with factory() as db:
            records = db.scalars(select(Information).where(Information.id >= low, Information.id < low + rows)).all()
            for row in records:
                db.delete(row)
            db.commit()
            for item in items:
                db.add(Information(**FIELDS, id=item['id'], user_id=7, username='bench', maxValue='55'))
            db.commit()
        return {'success': True}

    latencies, reads, statuses = [], [], {}
    stop = threading.Event()
    barrier = threading.Barrier(concurrency)

    with TestClient(app) as client:
        def read_probe():
            while not stop.is_set():
                start = time.perf_counter()
                response = client.get('/probe')
                if response.status_code != 200:
                    raise RuntimeError(response.text)
                reads.append((time.perf_counter() - start) * 1000)
                stop.wait(.005)

        def worker(index):
            result = []
            barrier.wait()
            for _ in range(iterations):
                start = time.perf_counter()
                response = client.post(f'/update/{index}')
                result.append((response.status_code, (time.perf_counter() - start) * 1000))
            return result

        with ThreadPoolExecutor(max_workers=concurrency + 1) as pool:
            reader = pool.submit(read_probe)
            try:
                futures = [pool.submit(worker, index) for index in range(concurrency)]
                for future in futures:
                    for status, latency in future.result():
                        statuses[str(status)] = statuses.get(str(status), 0) + 1
                        latencies.append(latency)
            finally:
                stop.set()
                reader.result()
    with factory() as db:
        plan = [list(row) for row in db.execute(text('EXPLAIN QUERY PLAN SELECT id FROM informations WHERE user_id=7 AND id IN (1,2)'))]
        remaining = db.query(Information).count()
    engine.dispose()
    return {'mode': mode, 'rows_per_request': rows, 'write_concurrency': concurrency, 'iterations_per_worker': iterations,
            'statuses': statuses, 'write_p50_ms': percentile(latencies, .5), 'write_p95_ms': percentile(latencies, .95),
            'probe_samples': len(reads), 'probe_p95_ms': percentile(reads, .95), 'sql_statements_including_reads': sql_count,
            'begin_immediate_wait_p95_ms': percentile(writer_waits, .95),
            'rows_after': remaining, 'id_query_plan': plan}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=int, choices=(1, 10, 50), default=50)
    parser.add_argument('--concurrency', type=int, choices=(1, 2, 4), default=2)
    parser.add_argument('--iterations', type=int, default=10)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--matrix', action='store_true', help='Run 1/10/50 rows at 1/2/4 concurrent writers')
    args = parser.parse_args()
    if not 1 <= args.iterations <= 100:
        parser.error('iterations must be 1..100')
    with tempfile.TemporaryDirectory(prefix='custom-benchmark-') as directory:
        cases = []
        combinations = [(r, c) for r in (1, 10, 50) for c in (1, 2, 4)] if args.matrix else [(args.rows, args.concurrency)]
        for rows, concurrency in combinations:
            case_directory = Path(directory) / f'{rows}-{concurrency}'
            case_directory.mkdir()
            cases.extend(run_case(case_directory, rows, concurrency, args.iterations, mode) for mode in ('legacy_two_commit', 'atomic'))
    # macOS reports ru_maxrss in bytes; Linux uses KiB. This is the whole process peak.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {'environment': {'platform': platform.platform(), 'python': platform.python_version()},
              'process_peak_rss_bytes': peak if sys.platform == 'darwin' else peak * 1024,
              'scope': 'local TestClient HTTP + temporary SQLite; not 2-core/2GB production measurement; RSS is shared process peak, not per request',
              'cases': cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
