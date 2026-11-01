"""Real SQLite lifecycle regressions without importing application startup."""
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import threading

import pytest


@pytest.fixture
def pool_factory(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "isolated_db_pool", Path(__file__).resolve().parents[1] / "app/sql/db_pool.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    connect = sqlite3.connect
    connections, pools = [], []

    class TrackedConnection(sqlite3.Connection):
        closed = False
        fail_setup = False
        fail_close = False

        def execute(self, sql, *args, **kwargs):
            if self.fail_setup and sql.startswith("PRAGMA"):
                raise sqlite3.OperationalError("setup failed")
            return super().execute(sql, *args, **kwargs)

        def close(self):
            if self.fail_close:
                raise sqlite3.OperationalError("close failed")
            super().close()
            self.closed = True

    def tracked_connect(*args, **kwargs):
        conn = connect(*args, factory=TrackedConnection, **kwargs)
        connections.append(conn)
        return conn

    monkeypatch.setattr(module.sqlite3, "connect", tracked_connect)

    def create(size=1):
        pool = module.SQLiteConnectionPool(str(tmp_path / "pool.db"), pool_size=size, timeout=0)
        pools.append(pool)
        return pool

    create.module = module
    create.connections = connections
    create.connect = tracked_connect
    yield create
    for conn in connections:
        conn.fail_close = False
    for pool in pools:
        pool.close_all()
    for conn in connections:
        conn.close()


def assert_live(pool, connections, expected):
    live = {conn for conn in connections if not conn.closed}
    assert len(live) == expected
    assert pool._all_conns == live
    assert pool._created_count == len(live)


def test_overflow_return_does_not_leak_or_exhaust_lifetime_creation_count(pool_factory):
    pool = pool_factory()
    for _ in range(100):
        with pool.get_connection() as first:
            with pool.get_connection() as overflow:
                assert first is not overflow
                assert_live(pool, pool_factory.connections, 2)
            assert not first.closed
        assert pool._pool.qsize() == 1
        assert_live(pool, pool_factory.connections, 1)
    pool.close_all()
    assert_live(pool, pool_factory.connections, 0)


def test_pool_exhaustion_preserves_timeout_error(pool_factory):
    pool = pool_factory()
    with pool.get_connection(), pool.get_connection():
        with pytest.raises(TimeoutError, match="waiting for a SQLite connection"):
            with pool.get_connection():
                pytest.fail("exhausted pool yielded a connection")


def test_closed_pool_rejects_borrow_with_original_error(pool_factory):
    pool = pool_factory()
    pool.close_all()
    with pytest.raises(RuntimeError, match="closing"):
        with pool.get_connection():
            pytest.fail("closed pool yielded a connection")


def test_business_exception_survives_shutdown_during_borrow(pool_factory):
    pool = pool_factory()
    with pytest.raises(ValueError, match="business failed"):
        with pool.get_connection():
            pool.close_all()
            raise ValueError("business failed")
    assert_live(pool, pool_factory.connections, 0)


def test_invalid_connection_is_replaced_without_count_drift(pool_factory):
    pool = pool_factory()
    for _ in range(10):
        with pool.get_connection() as conn:
            conn.close()
        assert_live(pool, pool_factory.connections, 1)
        with pool.get_connection() as replacement:
            assert replacement.execute("SELECT 1").fetchone()[0] == 1


def test_failed_replacement_does_not_leak_and_capacity_recovers(pool_factory, monkeypatch):
    pool = pool_factory()

    def fail_connect(*args, **kwargs):
        raise sqlite3.OperationalError("connect failed")

    with pool.get_connection() as conn:
        conn.close()
        monkeypatch.setattr(pool_factory.module.sqlite3, "connect", fail_connect)
    assert_live(pool, pool_factory.connections, 0)
    monkeypatch.setattr(pool_factory.module.sqlite3, "connect", pool_factory.connect)
    with pool.get_connection() as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    assert_live(pool, pool_factory.connections, 1)


def test_concurrent_returns_close_overflow_and_keep_queue_consistent(pool_factory):
    pool = pool_factory(size=2)
    with ThreadPoolExecutor(max_workers=4) as executor:
        for _ in range(20):
            borrowed = [pool.get_connection() for _ in range(4)]
            for context in borrowed:
                context.__enter__()
            barrier = threading.Barrier(4)

            def give_back(context):
                barrier.wait(timeout=3)
                context.__exit__(None, None, None)

            futures = [executor.submit(give_back, context) for context in borrowed]
            for future in futures:
                future.result(timeout=5)
            assert pool._pool.qsize() == 2
            assert_live(pool, pool_factory.connections, 2)


def test_shutdown_between_queue_get_and_yield_cannot_lend_closed_connection(pool_factory, monkeypatch):
    pool = pool_factory()
    got, release = threading.Event(), threading.Event()
    original_get = pool._pool.get

    def delayed_get(*args, **kwargs):
        conn = original_get(*args, **kwargs)
        got.set()
        assert release.wait(3)
        return conn

    monkeypatch.setattr(pool._pool, "get", delayed_get)

    def borrow():
        with pool.get_connection() as conn:
            conn.execute("SELECT 1")

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(borrow)
        try:
            assert got.wait(3)
            pool.close_all()
        finally:
            release.set()
        with pytest.raises(RuntimeError, match="closing"):
            future.result(timeout=5)
    assert_live(pool, pool_factory.connections, 0)


def test_pragma_failure_closes_new_connection_and_partial_initialization(pool_factory, monkeypatch):
    def fail_second_setup(*args, **kwargs):
        conn = pool_factory.connect(*args, **kwargs)
        conn.fail_setup = len(pool_factory.connections) == 2
        return conn

    monkeypatch.setattr(pool_factory.module.sqlite3, "connect", fail_second_setup)
    with pytest.raises(sqlite3.OperationalError, match="setup failed"):
        pool_factory(size=2)
    assert len(pool_factory.connections) == 2
    assert all(conn.closed for conn in pool_factory.connections)


def test_close_failure_remains_tracked_for_shutdown_retry(pool_factory, capsys):
    pool = pool_factory()
    conn = pool_factory.connections[0]
    conn.fail_close = True
    pool.close_all()
    assert "close failed" in capsys.readouterr().out
    assert_live(pool, pool_factory.connections, 1)
    conn.fail_close = False
    pool.close_all()
    assert_live(pool, pool_factory.connections, 0)
