import asyncio
import multiprocessing
import sqlite3
import threading
import time

import pytest
from app.common import fixed_default_cache as cache
from app.lifecycle import fixed_cache_warmup as warm
from tests.test_fixed_default_cache import MemoryRedis


def test_startup_populates_without_requests_and_skips_valid_entries(tmp_path, monkeypatch):
    path = tmp_path / 'test.db'
    with sqlite3.connect(path) as db:
        db.execute('create table items (n)')
    monkeypatch.setenv('FIXED_DEFAULT_LOCK_DIR', str(tmp_path / 'locks'))
    client = MemoryRedis()
    calls = []
    entries = [('sql:dialects_count', str(path), lambda db: calls.append(1) or {'count': 0})]
    async def run():
        handle = warm.start(entries=entries, client=client)
        await handle.task
        assert calls == [1]
        await warm.start(entries=entries, client=client).task
        assert calls == [1]
    asyncio.run(run())


def test_foreground_returns_while_warmer_still_running(tmp_path, monkeypatch):
    path = tmp_path / 'test.db'
    with sqlite3.connect(path) as db:
        db.execute('create table items (n)')
    monkeypatch.setenv('FIXED_DEFAULT_LOCK_DIR', str(tmp_path / 'locks'))
    entered, finish = threading.Event(), threading.Event()
    client = MemoryRedis()
    def load(db):
        entered.set()
        assert finish.wait(3)
        return {'count': 0}
    async def run():
        handle = warm.start(entries=[('sql:dialects_count', str(path), load)], client=client)
        assert await asyncio.to_thread(entered.wait, 2)
        try:
            assert await asyncio.wait_for(asyncio.to_thread(
                cache.call, 'sql:dialects_count', str(path), lambda: {'count': 0}, client=client), 1) == {'count': 0}
            assert not handle.task.done()
        finally:
            finish.set()
            await warm.stop(handle)
    asyncio.run(run())


def test_shutdown_interrupts_sql_and_releases_lock(tmp_path, monkeypatch):
    path = tmp_path / 'test.db'
    with sqlite3.connect(path) as db:
        db.execute('create table items (n)')
    monkeypatch.setenv('FIXED_DEFAULT_LOCK_DIR', str(tmp_path / 'locks'))
    entered = threading.Event()
    def load(db):
        entered.set()
        return db.execute('WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<1000000000) SELECT sum(x) FROM n').fetchone()[0]
    async def run():
        handle = warm.start(entries=[('sql:dialects_count', str(path), load)], client=MemoryRedis())
        assert await asyncio.to_thread(entered.wait, 2)
        await asyncio.wait_for(warm.stop(handle), 2)
        assert handle.task.done()
        with cache.publication_lock() as acquired:
            assert acquired
    asyncio.run(run())


def test_redis_failure_does_not_run_loader(tmp_path, monkeypatch):
    path = tmp_path / 'test.db'
    with sqlite3.connect(path):
        pass
    monkeypatch.setenv('FIXED_DEFAULT_LOCK_DIR', str(tmp_path / 'locks'))
    class Broken(MemoryRedis):
        def get(self, key):
            raise ConnectionError()
    calls = []
    async def run():
        await warm.start(entries=[('sql:dialects_count', str(path), lambda db: calls.append(1))], client=Broken()).task
    asyncio.run(run())
    assert not calls


def _hold_lock(root, entered, finish):
    import os
    os.environ['FIXED_DEFAULT_LOCK_DIR'] = root
    with cache.publication_lock() as acquired:
        assert acquired
        entered.set()
        finish.wait(5)


def test_only_one_host_background_owner(tmp_path, monkeypatch):
    root = str(tmp_path / 'locks')
    monkeypatch.setenv('FIXED_DEFAULT_LOCK_DIR', root)
    ctx = multiprocessing.get_context('spawn')
    entered, finish = ctx.Event(), ctx.Event()
    process = ctx.Process(target=_hold_lock, args=(root, entered, finish))
    process.start()
    try:
        assert entered.wait(3)
        with cache.publication_lock() as acquired:
            assert not acquired
    finally:
        finish.set()
        process.join(3)
        if process.is_alive():
            process.terminate()
            process.join()
    assert process.exitcode == 0


def test_vocabulary_background_yields_but_online_does_not(tmp_path, monkeypatch):
    from app.service.vocabulary.resources import run_bounded, BackgroundBusy
    monkeypatch.setenv('FIXED_DEFAULT_LOCK_DIR', str(tmp_path / 'fixed-locks'))
    monkeypatch.setenv('TOPONYMS_LOCK_DIR', str(tmp_path / 'heavy-locks'))
    calls = []
    async def run():
        with cache.publication_lock() as acquired:
            assert acquired
            with pytest.raises(BackgroundBusy):
                await run_bounded('test.db', lambda: calls.append('background'), background=True)
            assert await run_bounded('test.db', lambda: 'online') == 'online'
        assert not calls
    asyncio.run(run())


def test_query_timeout_continues_to_next_entry_without_caching_error(tmp_path, monkeypatch):
    path = tmp_path / 'test.db'
    with sqlite3.connect(path) as db:
        db.execute('create table items (n)')
    monkeypatch.setenv('FIXED_DEFAULT_LOCK_DIR', str(tmp_path / 'locks'))
    monkeypatch.setattr(warm, 'ITEM_BUDGET_SECONDS', 0.01)
    client = MemoryRedis()
    def slow(db):
        return db.execute('WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<1000000000) SELECT sum(x) FROM n').fetchone()[0]
    async def run():
        handle = warm.start(entries=[
            ('sql:query_stored_count', str(path), slow),
            ('sql:dialects_count', str(path), lambda db: {'count': 0}),
        ], client=client)
        try:
            await asyncio.wait_for(asyncio.shield(handle.task), 2)
        finally:
            await warm.stop(handle)
        assert cache.key('sql:query_stored_count') not in client.values
        assert cache.key('sql:dialects_count') in client.values
    asyncio.run(run())


def test_background_connection_cannot_write_main_database(tmp_path, monkeypatch):
    path = tmp_path / 'test.db'
    with sqlite3.connect(path) as db:
        db.execute('create table items (n)')
    monkeypatch.setenv('FIXED_DEFAULT_LOCK_DIR', str(tmp_path / 'locks'))
    client = MemoryRedis()
    def load(db):
        db.execute('insert into items values (1)')
        return {'count': 1}
    async def run():
        await warm.start(entries=[('sql:dialects_count', str(path), load)], client=client).task
    asyncio.run(run())
    with sqlite3.connect(path) as db:
        assert db.execute('select count(*) from items').fetchone()[0] == 0
    assert not client.values


def test_yubao_prewarm_limits_rows_and_individual_field_bytes(tmp_path, monkeypatch):
    from app.service.yubao import repository
    path = tmp_path / 'words.db'
    with sqlite3.connect(path) as db:
        db.execute('create table vocabulary(word text)')
        db.executemany('insert into vocabulary values (?)', [('一',), ('二',), ('三',)])
    monkeypatch.setattr(repository, 'WARMUP_MAX_ITEMS', 2)
    with warm._readonly(str(path), lambda: False) as db:
        repo = repository.YubaoRepository(connection=db, bounded_warmup=True)
        with pytest.raises(ValueError, match='warmup'):
            repo.list_distinct_words(q=None, limit=50, all_items=True)
    monkeypatch.setattr(repository, 'WARMUP_MAX_ITEMS', 20000)
    monkeypatch.setattr(repository, 'WARMUP_MAX_BYTES', 2)
    with warm._readonly(str(path), lambda: False) as db:
        with pytest.raises(ValueError, match='warmup'):
            repository.YubaoRepository(connection=db, bounded_warmup=True).list_distinct_words(q=None, limit=50, all_items=True)
    # Foreground remains complete, with no warmup truncation.
    with warm._readonly(str(path), lambda: False) as db:
        assert len(repository.YubaoRepository(connection=db).list_distinct_words(q=None, limit=50, all_items=True)) == 3


@pytest.mark.parametrize('vocabulary_start_fails', [False, True])
def test_lifespan_schedules_without_waiting_and_cleans_up_on_start_failure(monkeypatch, vocabulary_start_fails):
    from unittest.mock import AsyncMock, Mock
    from starlette.staticfiles import StaticFiles
    original_init = StaticFiles.__init__
    def static_init(self, *args, **kwargs):
        kwargs['check_dir'] = False  # Fresh worktrees need no copied frontend build.
        original_init(self, *args, **kwargs)
    monkeypatch.setattr(StaticFiles, '__init__', static_init)
    from app import main
    from app.service.vocabulary import cache_warmup
    from fastapi import FastAPI
    monkeypatch.setattr(main, '_RUN_TYPE', 'WEB')
    monkeypatch.setattr(main, 'is_gunicorn_worker_process', lambda: True)
    monkeypatch.setattr(main, 'shutdown_process_resources', AsyncMock())
    handle = object()
    start = Mock(return_value=handle)
    stop = AsyncMock()
    monkeypatch.setattr(warm, 'start', start)
    monkeypatch.setattr(warm, 'stop', stop)
    monkeypatch.setattr(cache_warmup, 'start_vocabulary_warmup',
                        AsyncMock(side_effect=RuntimeError('startup failed') if vocabulary_start_fails else None))
    monkeypatch.setattr(cache_warmup, 'stop_vocabulary_warmup', AsyncMock())
    async def run():
        lifespan = main._build_lifespan(lambda: None, enable_background_services=True)
        if vocabulary_start_fails:
            with pytest.raises(RuntimeError, match='startup failed'):
                async with lifespan(FastAPI()):
                    pytest.fail('startup failure must propagate')
        else:
            async with lifespan(FastAPI()):
                start.assert_called_once_with()
                stop.assert_not_called()
        stop.assert_awaited_once_with(handle)
    asyncio.run(run())
