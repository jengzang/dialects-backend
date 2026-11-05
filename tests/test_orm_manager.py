import gc
import sqlite3
import weakref
from unittest.mock import Mock

import pytest
from sqlalchemy import text
from sqlalchemy.pool import QueuePool, SingletonThreadPool

from app.common import sqlite_orm as orm


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    monkeypatch.setattr(orm, '_engines', weakref.WeakKeyDictionary())
    dispose = orm.dispose_all_orm_engines
    yield
    dispose()


@pytest.mark.parametrize('profile,timeout,foreign_keys,cache_size', [
    ('auth', 5000, 1, -2000), ('logs', 5000, 0, -2000),
    ('supplements', 5000, 1, -2000), ('vocabulary', 10000, 1, -2000),
])
def test_profiles_use_2000kib_cache_preserve_other_settings_and_create_lazily(tmp_path, profile, timeout, foreign_keys, cache_size):
    path = tmp_path / (profile + '.db')
    engine, factory = orm.create_engine_and_session(profile, f'sqlite:///{path}')
    assert not path.exists()
    assert orm.POLICIES[profile].cache_kib == 2000
    assert factory.kw['bind'] is engine
    assert isinstance(engine.pool, QueuePool)
    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 10
    assert engine.pool._timeout == 30
    assert engine.pool.checkedout() == 0
    with engine.connect() as db:
        assert db.exec_driver_sql('pragma busy_timeout').scalar() == timeout
        assert db.exec_driver_sql('pragma foreign_keys').scalar() == foreign_keys
        assert db.exec_driver_sql('pragma journal_mode').scalar() == 'wal'
        assert db.exec_driver_sql('pragma synchronous').scalar() == 1
        if cache_size is None:
            with sqlite3.connect(':memory:') as reference:
                cache_size = reference.execute('pragma cache_size').fetchone()[0]
        assert db.exec_driver_sql('pragma cache_size').scalar() == cache_size


def test_sessions_are_independent_and_do_not_commit_implicitly(tmp_path):
    engine, factory = orm.create_engine_and_session('auth', f"sqlite:///{tmp_path / 'auth.db'}")
    with engine.begin() as db:
        db.exec_driver_sql('create table items (n)')
    with factory() as first:
        first.execute(text('insert into items values (1)'))
        first.commit()
    with pytest.raises(RuntimeError):
        with factory() as second:
            second.execute(text('insert into items values (2)'))
            raise RuntimeError('abort')
    with factory() as third:
        assert third.scalar(text('select count(*) from items')) == 1
    bound_factory = orm.make_session_factory(engine)
    assert bound_factory.kw['bind'] is engine
    assert bound_factory.kw['autoflush'] is False
    assert bound_factory.kw['expire_on_commit'] is True


def test_in_memory_database_keeps_its_existing_pool_and_data():
    engine, factory = orm.create_engine_and_session('supplements', 'sqlite:///:memory:')
    assert isinstance(engine.pool, SingletonThreadPool)
    with engine.begin() as db:
        db.exec_driver_sql('create table items (n)')
        db.exec_driver_sql('insert into items values (1)')
    with factory() as db:
        assert db.scalar(text('select count(*) from items')) == 1


def test_registry_does_not_keep_temporary_engines_alive(tmp_path):
    engine, factory = orm.create_engine_and_session('vocabulary', f"sqlite:///{tmp_path / 'test.db'}")
    ref = weakref.ref(engine)
    del factory, engine
    gc.collect()
    assert ref() is None
    assert orm.pool_status() == []


def test_pool_status_has_no_connection_side_effect_and_dispose_releases_idle_handles(tmp_path):
    engine, factory = orm.create_engine_and_session('auth', f"sqlite:///{tmp_path / 'test.db'}")
    assert orm.pool_status()[0]['checked_out'] == 0
    assert not (tmp_path / 'test.db').exists()
    with factory() as db:
        db.scalar(text('select 1'))
        assert orm.pool_status()[0]['checked_out'] == 1
    old_pool = engine.pool
    assert old_pool.checkedin() == 1
    assert orm.dispose_all_orm_engines() == {'disposed': 1, 'failed': 0}
    assert old_pool.checkedin() == 0
    # Module-level factories remain usable if the app lifespan starts again.
    with factory() as db:
        assert db.scalar(text('select 1')) == 1


def test_dispose_continues_after_one_engine_fails():
    bad, good = Mock(), Mock()
    bad.dispose.side_effect = RuntimeError('close failed')
    orm._engines[bad] = 'auth'
    orm._engines[good] = 'logs'
    assert orm.dispose_all_orm_engines() == {'disposed': 1, 'failed': 1}
    good.dispose.assert_called_once()


def test_invalid_profile_and_non_sqlite_urls_fail_before_any_connection(tmp_path):
    with pytest.raises(ValueError):
        orm.create_engine_and_session('unregistered', f"sqlite:///{tmp_path / 'no.db'}")
    with pytest.raises(ValueError):
        orm.create_engine_and_session('auth', 'postgresql://localhost/test')
    assert not (tmp_path / 'no.db').exists()


def test_wal_fallback_and_cursor_cleanup():
    connection = Mock()
    cursor = connection.cursor.return_value
    def execute(sql):
        if sql == 'PRAGMA journal_mode=WAL':
            raise sqlite3.OperationalError('WAL unavailable')
    cursor.execute.side_effect = execute
    orm._configure_connection(connection, orm.POLICIES['auth'], 'auth')
    assert any(call.args == ('PRAGMA journal_mode=DELETE',) for call in cursor.execute.call_args_list)
    cursor.close.assert_called_once()


def test_failed_connection_configuration_closes_cursor_and_propagates():
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.execute.side_effect = sqlite3.OperationalError('database locked')
    with pytest.raises(sqlite3.OperationalError):
        orm._configure_connection(connection, orm.POLICIES['auth'], 'auth')
    cursor.close.assert_called_once()


def test_concurrent_sessions_return_all_connections(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    engine, factory = orm.create_engine_and_session('auth', f"sqlite:///{tmp_path / 'concurrent.db'}")
    # Initialize WAL before testing concurrent reads rather than racing file creation.
    with engine.begin() as db:
        db.exec_driver_sql('create table items (n)')
    barrier = Barrier(4)
    def query(_):
        with factory() as db:
            value = db.scalar(text('select count(*) from items'))
            barrier.wait(timeout=5)
            return value
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(query, range(4))) == [0] * 4
    assert engine.pool.checkedout() == 0
    assert engine.pool.checkedin() == 4


@pytest.mark.parametrize('failure', ['redis', 'orm', None])
def test_shutdown_always_releases_raw_pools(monkeypatch, failure):
    import asyncio
    from unittest.mock import AsyncMock
    from app.lifecycle import startup
    from app.common import fixed_default_cache
    calls = []
    monkeypatch.setattr(fixed_default_cache, 'close_client', lambda: calls.append('fixed'))
    monkeypatch.setattr(startup, 'close_redis', AsyncMock(side_effect=RuntimeError('redis') if failure == 'redis' else None))
    def dispose():
        calls.append('orm')
        if failure == 'orm':
            raise RuntimeError('orm')
    monkeypatch.setattr(orm, 'dispose_all_orm_engines', dispose)
    monkeypatch.setattr(startup, 'close_all_pools', lambda: calls.append('raw'))
    if failure:
        with pytest.raises(RuntimeError, match=failure):
            asyncio.run(startup.shutdown_process_resources())
    else:
        asyncio.run(startup.shutdown_process_resources())
    assert calls == ['fixed', 'orm', 'raw']
