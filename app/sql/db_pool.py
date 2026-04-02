"""SQLite connection pool utilities."""

import sqlite3
import threading
from contextlib import contextmanager
from queue import Empty, Queue
from typing import Iterator


class SQLiteConnectionPool:
    """Simple SQLite connection pool with shutdown-aware cleanup."""

    def __init__(self, db_path: str, pool_size: int = 10, timeout: float = 30.0):
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool: Queue[sqlite3.Connection] = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._created_count = 0
        self._closing = False
        self._all_conns: set[sqlite3.Connection] = set()

        for _ in range(pool_size):
            self._pool.put(self._create_connection())
            self._created_count += 1

    def _create_connection(self) -> sqlite3.Connection:
        if self._closing:
            raise RuntimeError("Cannot create SQLite connections while the pool is closing")

        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-16000")
        conn.execute("PRAGMA temp_store=MEMORY")
        self._all_conns.add(conn)
        return conn

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = None
        try:
            if self._closing:
                raise RuntimeError(f"SQLite connection pool is closing for {self.db_path}")

            try:
                conn = self._pool.get(timeout=self.timeout)
            except Empty:
                with self._lock:
                    if self._closing:
                        raise RuntimeError(f"SQLite connection pool is closing for {self.db_path}")
                    if self._created_count < self.pool_size * 2:
                        conn = self._create_connection()
                        self._created_count += 1
                    else:
                        raise TimeoutError(
                            f"Timed out after {self.timeout} seconds waiting for a SQLite connection"
                        )

            yield conn
        finally:
            if conn is None:
                return

            if self._closing:
                self._discard_connection(conn)
                return

            try:
                conn.execute("SELECT 1")
                self._pool.put(conn, block=False)
            except Exception:
                self._discard_connection(conn)
                try:
                    if not self._closing:
                        new_conn = self._create_connection()
                        self._pool.put(new_conn, block=False)
                except Exception:
                    pass

    def _discard_connection(self, conn: sqlite3.Connection) -> None:
        try:
            conn.close()
        except KeyboardInterrupt:
            print(f"[WARN] Shutdown interrupted while closing SQLite connection: {self.db_path}")
        except Exception as exc:
            print(f"[WARN] Failed to close SQLite connection: {self.db_path}: {exc}")
        finally:
            self._all_conns.discard(conn)

    def close_all(self) -> None:
        self._closing = True

        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
            except Empty:
                break
            self._discard_connection(conn)

        for conn in list(self._all_conns):
            self._discard_connection(conn)


class DatabasePoolManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._pools: dict[str, SQLiteConnectionPool] = {}
        self._initialized = True

    def get_pool(self, db_path: str, pool_size: int = 10) -> SQLiteConnectionPool:
        if db_path not in self._pools:
            with self._lock:
                if db_path not in self._pools:
                    self._pools[db_path] = SQLiteConnectionPool(db_path, pool_size)
        return self._pools[db_path]

    def close_all(self) -> None:
        for pool in self._pools.values():
            pool.close_all()
        self._pools.clear()


db_pool_manager = DatabasePoolManager()


def get_db_pool(db_path: str, pool_size: int = 10) -> SQLiteConnectionPool:
    return db_pool_manager.get_pool(db_path, pool_size)


def close_all_pools() -> None:
    db_pool_manager.close_all()
