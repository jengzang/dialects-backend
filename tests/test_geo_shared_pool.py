"""Read-only profile integration and request-state isolation."""
import sqlite3
from pathlib import Path

import pytest

from app.sql import db_pool
from app.service.toponyms import resources


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'read # ?.db'
    with sqlite3.connect(path) as db:
        db.execute('create table items (value)')
        db.execute('insert into items values (1)')
    yield path
    db_pool.close_all_pools()


def test_profiles_are_lazy_readonly_and_keep_small_cache(database):
    pool = db_pool.get_readonly_db_pool(database, 'toponyms')
    assert pool._created_count == 0
    assert pool is db_pool.get_readonly_db_pool(str(database), 'toponyms')
    with pool.get_connection() as conn:
        assert conn.execute('pragma cache_size').fetchone()[0] == -4096
        assert conn.execute('pragma temp_store').fetchone()[0] == 1
        assert conn.execute('pragma busy_timeout').fetchone()[0] == 100
        assert conn.execute('pragma journal_mode').fetchone()[0] == 'delete'
        conn.execute('pragma query_only=OFF')
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('insert into items values (2)')
    assert pool._created_count == 1


def test_profile_capacity_and_return_cleanup(database):
    pool = db_pool.get_readonly_db_pool(database, 'toponyms')
    for _ in range(10):
        with pool.get_connection() as one, pool.get_connection(), pool.get_connection():
            with pytest.raises(TimeoutError):
                with pool.get_connection():
                    pass
            one.set_progress_handler(lambda: 1, 1)
            one.set_trace_callback(lambda sql: None)
            one.set_authorizer(lambda *args: sqlite3.SQLITE_DENY)
        assert pool._created_count == 1
        assert pool._pool.qsize() == 1
    with pool.get_connection() as conn:
        assert conn.execute('select sum(value) from items').fetchone()[0] == 1


def test_toponym_deadline_and_stream_handlers_do_not_survive_return(database):
    with resources.connection(database) as first:
        assert first.execute('select count(*) from items').fetchone()[0] == 1
    with resources.connection(database) as second:
        assert first is second
        assert second.execute('select 1').fetchone()[0] == 1


def test_atomic_replacement_is_seen_and_active_read_is_not_closed(database):
    pool = db_pool.get_readonly_db_pool(database, 'toponyms')
    with pool.get_connection() as old:
        replacement = database.with_name('replacement.db')
        with sqlite3.connect(replacement) as db:
            db.execute('create table items (value)')
            db.execute('insert into items values (99)')
        replacement.replace(database)
        assert old.execute('select value from items').fetchone()[0] == 1
        with pool.get_connection() as new:
            assert new.execute('select value from items').fetchone()[0] == 99
    with pytest.raises(sqlite3.ProgrammingError):
        old.execute('select 1')
    assert pool._created_count == 1


def test_gis_profile_separate_and_reacquired_after_shutdown(database):
    pool = db_pool.get_readonly_db_pool(database, 'gis')
    assert pool is not db_pool.get_readonly_db_pool(database, 'toponyms')
    with pool.get_connection() as conn:
        assert conn.execute('pragma busy_timeout').fetchone()[0] == 5000
    db_pool.close_all_pools()
    new = db_pool.get_readonly_db_pool(database, 'gis')
    assert new is not pool
    with new.get_connection() as conn:
        assert conn.execute('select 1').fetchone()[0] == 1


def test_readonly_exception_closed_handle_and_transaction_are_cleaned(database):
    pool = db_pool.get_readonly_db_pool(database, 'toponyms')
    with pytest.raises(ValueError, match='business'):
        with pool.get_connection() as conn:
            conn.execute('begin')
            raise ValueError('business')
    with pool.get_connection() as conn:
        assert not conn.in_transaction
        conn.close()
    assert pool._created_count == 0
    with pool.get_connection() as conn:
        assert conn.execute('select 1').fetchone()[0] == 1


def test_readonly_idle_replacement_drops_old_handles(database):
    pool = db_pool.get_readonly_db_pool(database, 'toponyms')
    with pool.get_connection() as first:
        pass
    replacement = database.with_name('replacement.db')
    with sqlite3.connect(replacement) as db:
        db.execute('create table items (value)')
        db.execute('insert into items values (2)')
    replacement.replace(database)
    with pool.get_connection() as second:
        assert second is not first
        assert second.execute('select value from items').fetchone()[0] == 2
    with pytest.raises(sqlite3.ProgrammingError):
        first.execute('select 1')


def test_gis_engines_share_registered_pool_and_restart_cleanly(database):
    from app.geo_query.engine import AreaCityQueryPy
    with sqlite3.connect(database) as db:
        db.execute('create table meta (key text, value text)')
        db.execute('insert into meta values ("feature_count", "1")')
    first, second = AreaCityQueryPy(), AreaCityQueryPy()
    first.init_store(database)
    second.init_store(database)
    pool = db_pool.get_readonly_db_pool(database, 'gis')
    assert pool._created_count == 1
    db_pool.close_all_pools()
    with first._get_conn() as conn:
        assert conn.execute('select value from items').fetchone()[0] == 1
    assert db_pool.get_readonly_db_pool(database, 'gis') is not pool


def test_missing_readonly_database_does_not_create_file(tmp_path):
    path = tmp_path / 'missing.db'
    pool = db_pool.get_readonly_db_pool(path, 'toponyms')
    try:
        with pytest.raises((OSError, sqlite3.OperationalError)):
            with pool.get_connection():
                pass
        assert not path.exists()
        assert pool._created_count == 0
    finally:
        db_pool.close_all_pools()


def test_gis_overflow_returns_are_bounded_and_no_error_is_suppressed(database):
    from contextlib import ExitStack
    pool = db_pool.get_readonly_db_pool(database, 'gis')
    pool.timeout = 0
    for _ in range(20):
        with ExitStack() as stack:
            for _ in range(6):
                stack.enter_context(pool.get_connection())
            assert pool._created_count == 6
            with pytest.raises(TimeoutError):
                with pool.get_connection():
                    pass
        assert pool._created_count == 3
        assert pool._pool.qsize() == 3
    with pytest.raises(ValueError, match='business'):
        with pool.get_connection():
            raise ValueError('business')
    assert pool._created_count == 3


def test_partly_consumed_cursor_is_closed_before_connection_reuse(database):
    pool = db_pool.get_readonly_db_pool(database, 'toponyms')
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('select value from items union all select 2')
        assert cursor.fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        cursor.fetchone()
    with pool.get_connection() as conn:
        cursor = conn.execute('select value from items union all select 3')
        assert cursor.fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        cursor.fetchone()


def test_invalid_profile_budget_is_rejected(database):
    with pytest.raises(ValueError):
        db_pool.SQLiteConnectionPool(database, readonly_profile=db_pool.ReadOnlyProfile(0, 3, 0, .1))


def test_gis_replacement_does_not_mix_geometry_or_metadata(database):
    import json
    from types import SimpleNamespace
    from app.geo_query.engine import AreaCityQueryPy
    from app.geo_query.cache import LRUCache
    def populate(path, version):
        with sqlite3.connect(path) as db:
            db.execute('create table meta (key text, value text)')
            db.execute('insert into meta values (?, ?)', ('version', json.dumps(version)))
            db.execute('create table subgeometries (sub_id integer primary key, geom_blob blob)')
            db.execute('insert into subgeometries values (?, ?)',
                       (1, json.dumps({'type': 'Point', 'coordinates': [version, version]}).encode()))
    populate(database, 1)
    engine = AreaCityQueryPy()
    engine.init_store(database)
    engine._geometry_cache = LRUCache(1)
    record = SimpleNamespace(sub_id=1)
    with engine._get_conn() as old:
        assert engine._load_geometry(old, record)['coordinates'] == [1, 1]
        replacement = database.with_name('replacement.db')
        populate(replacement, 2)
        replacement.replace(database)
        with engine._get_conn() as new:
            assert engine._load_geometry(new, record)['coordinates'] == [2, 2]
            assert engine.meta['version'] == 2
            # A late old request may refill the shared LRU, but cannot poison
            # a new generation's key or expand the global entry budget.
            assert engine._load_geometry(old, record)['coordinates'] == [1, 1]
            assert engine._load_geometry(new, record)['coordinates'] == [2, 2]
            assert len(engine._geometry_cache) == 1


def test_readonly_parallel_borrowers_are_exclusive_and_return_to_idle_budget(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    pool = db_pool.get_readonly_db_pool(database, 'toponyms')
    with ThreadPoolExecutor(max_workers=3) as executor:
        for _ in range(10):
            barrier = Barrier(3)
            def query(_):
                with pool.get_connection() as conn:
                    assert conn.execute('select value from items').fetchone()[0] == 1
                    identity = id(conn)
                    barrier.wait(timeout=5)
                    return identity
            assert len(set(executor.map(query, range(3)))) == 3
            assert pool._created_count == 1
            assert pool._pool.qsize() == 1


def test_toponym_pool_saturation_remains_query_busy_and_stream_releases_slot(database):
    from app.service.toponyms.streaming import QueryStream
    from contextlib import ExitStack
    pool = db_pool.get_readonly_db_pool(database, 'toponyms')
    with ExitStack() as stack:
        for _ in range(3):
            stack.enter_context(pool.get_connection())
        with pytest.raises(resources.QueryBusy):
            with resources.connection(database):
                pass
        reader = QueryStream(str(database), 'names', {'query': '村', 'match_mode': 'contains', 'limit': 0})
        with pytest.raises(resources.QueryBusy):
            reader.start()
    with resources.execution_slot(database, 'heavy'), resources.execution_slot(database, 'heavy'):
        pass
