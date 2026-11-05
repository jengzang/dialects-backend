"""Local ORM cache sweep: source files read-only, writes on synthetic TEMP DBs.

Sequential fresh subprocess per profile/budget/round. No application startup,
production access, source DB copies, cache clearing, concurrency, or retries.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import configure_mappers, sessionmaker
from sqlalchemy.pool import QueuePool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.common.sqlite_orm import SQLitePolicy, _configure_connection
from benchmark_db_cache import identity, rss_mib

PROFILES = {
    'auth': ('auth.db', 'app/service/auth/database/models.py'),
    'logs': ('logs.db', 'app/service/logging/core/models.py'),
    'supplements': ('supplements.db', 'app/service/user/core/models.py'),
    'vocabulary': ('vocabulary.db', 'app/service/vocabulary/models.py'),
}


def models(profile):
    spec = importlib.util.spec_from_file_location('bench_models_' + profile, ROOT / PROFILES[profile][1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    configure_mappers()
    return module


def read_cases(profile, m, session):
    if profile == 'logs':
        return {
            'keywords_top10': select(m.ApiKeywordLog.value, func.count()).group_by(m.ApiKeywordLog.value).order_by(func.count().desc(), m.ApiKeywordLog.value).limit(10),
            'diagnostics_latest50': select(m.ApiDiagnosticEvent).order_by(m.ApiDiagnosticEvent.id.desc()).limit(50),
        }
    if profile == 'auth':
        return {
            'users20_with_joined_summary': select(m.User).order_by(m.User.id).limit(20),
            'usage_latest50': select(m.ApiUsageLog).order_by(m.ApiUsageLog.id.desc()).limit(50),
            'usage_count': select(func.count()).select_from(m.ApiUsageLog),
        }
    if profile == 'supplements':
        return {
            'information_page50': select(m.Information).order_by(m.Information.id).limit(50),
            'region_page50': select(m.UserRegion).order_by(m.UserRegion.id).limit(50),
        }
    location = session.scalar(select(m.VocabularyEntry.location_name).order_by(m.VocabularyEntry.id).limit(1))
    return {
        'latest50': select(m.VocabularyEntry).order_by(m.VocabularyEntry.id.desc()).limit(50),
        'location50': select(m.VocabularyEntry).where(m.VocabularyEntry.location_name == location).order_by(m.VocabularyEntry.id).limit(50),
        'contains_count': select(func.count()).select_from(m.VocabularyEntry).where(m.VocabularyEntry.local_expression.contains('山')),
    }


def result_signature(rows):
    # Compare scalar results / entity IDs, without exposing user fields.
    values = [tuple(getattr(value, 'id', value) for value in row) for row in rows]
    return hashlib.sha256(repr(values).encode()).hexdigest()


def read_run(profile, m, path, cache):
    before = identity(path)
    uri = path.resolve(strict=True).as_uri() + '?mode=ro'
    engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(uri, uri=True),
                          poolclass=QueuePool, pool_size=1, max_overflow=0)
    @event.listens_for(engine, 'connect')
    def configure(conn, _):
        conn.execute('PRAGMA query_only=ON')
        conn.execute(f'PRAGMA cache_size=-{cache}')
    baseline = rss_mib()
    results = {}
    try:
        with sessionmaker(bind=engine, autoflush=False)() as session:
            cases = read_cases(profile, m, session)
        for name, statement in cases.items():
            timings, signatures = [], []
            for _ in range(6):
                # ORM session per query, underlying handle reused by the pool.
                with sessionmaker(bind=engine, autoflush=False)() as session:
                    handle = session.connection().connection.driver_connection
                    deadline = time.monotonic() + 3
                    handle.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10000)
                    try:
                        started = time.perf_counter()
                        rows = session.execute(statement).unique().all()
                        timings.append((time.perf_counter() - started) * 1000)
                        signatures.append(result_signature(rows))
                        del rows
                    finally:
                        handle.set_progress_handler(None, 0)
            assert len(set(signatures)) == 1
            results[name] = {'first_ms': timings[0], 'warm_median_ms': statistics.median(timings[1:]), 'signature': signatures[0]}
        delta = rss_mib() - baseline
    finally:
        engine.dispose()
    assert identity(path) == before, 'Source database identity changed during read-only run'
    return {'rss_delta_mib': delta, 'queries': results}


def write_mappings(profile, m, offset, size):
    if profile == 'logs':
        return m.ApiKeywordLog, [dict(timestamp=datetime(2026, 1, 1), path='/vocabulary/search', field='word', value=f'山{i % 500}'+ 'a' * 128) for i in range(offset, offset + size)]
    if profile == 'auth':
        return m.ApiUsageLog, [dict(path='/vocabulary/search', duration=0.1, status_code=200, ip='127.0.0.1', user_agent='synthetic', request_size=100, response_size=1024) for _ in range(size)]
    if profile == 'supplements':
        return m.Information, [dict(簡稱=f'地点{i % 100}', 音典分區='区', 經緯度='1,2', 特徵='声母', 值='a' * 256, maxValue='a', user_id=1, username='synthetic') for i in range(offset, offset + size)]
    return m.VocabularyEntry, [dict(user_id=1, location_name=f'地点{i % 100}', standard_word=f'词{i % 1000}', local_expression='山' + 'a' * 128, ipa='a', notes='n' * 128) for i in range(offset, offset + size)]


def write_run(profile, m, cache, seed_rows=12000, batches=20):
    with tempfile.TemporaryDirectory(prefix='orm-cache-synthetic-') as temp:
        engine = create_engine(f'sqlite:///{Path(temp) / "synthetic.db"}', poolclass=QueuePool, pool_size=1, max_overflow=0)
        policy = SQLitePolicy(cache_kib=cache, foreign_keys=None if profile == 'logs' else True)
        event.listen(engine, 'connect', lambda conn, _: _configure_connection(conn, policy, profile))
        try:
            m.Base.metadata.create_all(engine)
            baseline = rss_mib()
            factory = sessionmaker(bind=engine, autoflush=False)
            for offset in range(0, seed_rows, 512):
                model, items = write_mappings(profile, m, offset, min(512, seed_rows - offset))
                with factory() as session:
                    session.bulk_insert_mappings(model, items)
                    session.commit()
            batch_size = {'logs': 50, 'auth': 50, 'supplements': 10, 'vocabulary': 512}[profile]
            times = []
            # Vocabulary import batches share a single transaction in production.
            with factory() as session:
                for index in range(batches):
                    model, items = write_mappings(profile, m, seed_rows + index * batch_size, batch_size)
                    objects = [model(**row) for row in items] if profile in {'auth', 'logs'} else None
                    started = time.perf_counter()
                    if objects is not None:
                        session.bulk_save_objects(objects)
                    else:
                        session.bulk_insert_mappings(model, items)
                    if profile != 'vocabulary':
                        session.commit()
                    times.append((time.perf_counter() - started) * 1000)
                started = time.perf_counter()
                session.commit()
                final_commit_ms = (time.perf_counter() - started) * 1000
            # Failed transaction must not leave a partial batch.
            with factory() as session:
                model, items = write_mappings(profile, m, 0, 1)
                session.bulk_insert_mappings(model, items)
                session.rollback()
            with factory() as session:
                count = session.scalar(select(func.count()).select_from(model))
                assert count == seed_rows + batches * batch_size
            diagnostics = None
            if profile == 'logs':
                diag_times = []
                for _ in range(batches):
                    events = [m.ApiDiagnosticEvent(
                        occurred_at=datetime(2026, 1, 1), event_type='slow',
                        path='/vocabulary/search', method='GET', duration_ms=2100,
                        request_body_text='x' * 2048,
                    ) for _ in range(25)]
                    with factory() as session:
                        started = time.perf_counter()
                        session.bulk_save_objects(events)
                        session.commit()
                        diag_times.append((time.perf_counter() - started) * 1000)
                with factory() as session:
                    assert session.scalar(select(func.count()).select_from(m.ApiDiagnosticEvent)) == batches * 25
                diagnostics = {'batch_size': 25, 'body_bytes': 2048,
                               'median_ms': statistics.median(diag_times), 'max_ms': max(diag_times)}
            return {'batch_size': batch_size, 'batch_median_ms': statistics.median(times),
                    'batch_max_ms': max(times), 'final_commit_ms': final_commit_ms,
                    'rss_delta_mib': rss_mib() - baseline, 'verified_rows': count,
                    'diagnostics': diagnostics}
        finally:
            engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--profile', choices=PROFILES)
    parser.add_argument('--cache', type=int)
    parser.add_argument('--phase', choices=['read', 'write'], default='read')
    args = parser.parse_args()
    if args.profile:
        m = models(args.profile)
        result = (read_run(args.profile, m, args.data_root / PROFILES[args.profile][0], args.cache)
                  if args.phase == 'read' else write_run(args.profile, m, args.cache))
        print(json.dumps(result))
        return
    assert args.output
    results = []
    for round_index in range(3):
        for profile in PROFILES:
            budgets = [2000, 4096, 8192, 16000] + ([64000] if profile == 'logs' else [])
            # Reverse alternate rounds to reduce ordering bias; OS cache stays warm.
            for cache in budgets[::(-1 if round_index % 2 else 1)]:
                item = {'profile': profile, 'cache_kib': cache}
                for phase in ('read', 'write'):
                    proc = subprocess.run([sys.executable, __file__, '--data-root', str(args.data_root), '--profile', profile, '--cache', str(cache), '--phase', phase], capture_output=True, text=True, timeout=60, check=True)
                    item[phase] = json.loads(proc.stdout)
                item['round'] = round_index + 1
                results.append(item)
                print(f'round {round_index + 1} {profile} {cache}', flush=True)
    signatures = {}
    for result in results:
        for name, query in result['read']['queries'].items():
            signatures.setdefault((result['profile'], name), set()).add(query['signature'])
    assert all(len(values) == 1 for values in signatures.values()), 'Read results differ between budgets'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'runs': results}, indent=2) + '\n')


if __name__ == '__main__':
    main()
