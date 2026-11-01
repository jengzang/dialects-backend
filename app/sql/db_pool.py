"""SQLite connection pool utilities."""

import sqlite3
import threading
from contextlib import contextmanager
from queue import Empty, Full, Queue
from typing import Iterator


class SQLiteConnectionPool:
    """Simple SQLite connection pool with shutdown-aware cleanup."""

    def __init__(self, db_path: str, pool_size: int = 10, timeout: float = 30.0):
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool: Queue[sqlite3.Connection] = Queue(maxsize=pool_size)
        # Creation, return and shutdown share the same lifecycle lock. Helpers
        # take it too so they cannot race close_all or drift the live count.
        self._lock = threading.RLock()
        self._created_count = 0
        self._closing = False
        self._all_conns: set[sqlite3.Connection] = set()

        try:
            for _ in range(pool_size):
                self._pool.put(self._create_connection())
        except BaseException:
            self.close_all()
            raise

    def _create_connection(self) -> sqlite3.Connection:
        with self._lock:
            if self._closing:
                raise RuntimeError("Cannot create SQLite connections while the pool is closing")

            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            try:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=-16000")
                conn.execute("PRAGMA temp_store=MEMORY")
            except BaseException:
                conn.close()
                raise
            self._all_conns.add(conn)
            self._created_count = len(self._all_conns)
            return conn

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            if self._closing:
                raise RuntimeError(f"SQLite connection pool is closing for {self.db_path}")

        # Never hold the lifecycle lock while waiting for a borrower to return.
        try:
            conn = self._pool.get(timeout=self.timeout)
        except Empty:
            with self._lock:
                if self._closing:
                    raise RuntimeError(f"SQLite connection pool is closing for {self.db_path}")
                try:
                    # A return may have won the lock after the timed wait.
                    conn = self._pool.get_nowait()
                except Empty:
                    if len(self._all_conns) < self.pool_size * 2:
                        conn = self._create_connection()
                    else:
                        raise TimeoutError(
                            f"Timed out after {self.timeout} seconds waiting for a SQLite connection"
                        )

        with self._lock:
            if self._closing:
                self._discard_connection(conn)
                raise RuntimeError(f"SQLite connection pool is closing for {self.db_path}")
        try:
            yield conn
        finally:
            # Cleanup must not return from this generator: doing so suppresses
            # exceptions raised by the caller, including during shutdown.
            self._return_connection(conn)

    def _return_connection(self, conn: sqlite3.Connection) -> None:
        with self._lock:
            if conn not in self._all_conns:
                return  # close_all already closed this checked-out connection.
            if self._closing:
                self._discard_connection(conn)
                return

            try:
                conn.execute("SELECT 1")
            except Exception:
                self._discard_connection(conn)
                replacement = None
                try:
                    if not self._pool.full() and len(self._all_conns) < self.pool_size * 2:
                        replacement = self._create_connection()
                        self._pool.put_nowait(replacement)
                except Exception:
                    if replacement is not None:
                        self._discard_connection(replacement)
                return

            try:
                self._pool.put_nowait(conn)
            except Full:
                # Overflow is healthy but no longer needed. Do not create a
                # replacement for a queue that is already full.
                self._discard_connection(conn)

    def _discard_connection(self, conn: sqlite3.Connection) -> None:
        with self._lock:
            try:
                conn.close()
            except KeyboardInterrupt:
                print(f"[WARN] Shutdown interrupted while closing SQLite connection: {self.db_path}")
            except Exception as exc:
                print(f"[WARN] Failed to close SQLite connection: {self.db_path}: {exc}")
            else:
                self._all_conns.discard(conn)
                self._created_count = len(self._all_conns)

    def close_all(self) -> None:
        with self._lock:
            self._closing = True

            while True:
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
