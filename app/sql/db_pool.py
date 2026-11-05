"""SQLite connection pool utilities."""

import sqlite3
import time
import weakref
from pathlib import Path
from typing import NamedTuple
from types import MappingProxyType
import threading
from contextlib import contextmanager
from queue import Empty, Full, Queue
from typing import Iterator


class ReadOnlyProfile(NamedTuple):
    idle_connections: int
    max_connections: int
    wait_seconds: float
    busy_seconds: float
    cache_kib: int = 2000


READONLY_PROFILES = MappingProxyType({
    'toponyms': ReadOnlyProfile(1, 3, 0.0, 0.1, cache_kib=4096),
    'gis': ReadOnlyProfile(3, 6, 5.0, 5.0),
})


class _ReadOnlyConnection(sqlite3.Connection):
    """Track live cursors so interrupted Python iteration releases read locks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cursors = weakref.WeakSet()

    def cursor(self, *args, **kwargs):
        cursor = super().cursor(*args, **kwargs)
        self._cursors.add(cursor)
        return cursor

    def _execute(self, method, *args, **kwargs):
        cursor = self.cursor()
        try:
            return getattr(cursor, method)(*args, **kwargs)
        except BaseException:
            cursor.close()
            raise

    def execute(self, *args, **kwargs):
        return self._execute('execute', *args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._execute('executemany', *args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self._execute('executescript', *args, **kwargs)

    def close_cursors(self):
        for cursor in list(self._cursors):
            cursor.close()
        self._cursors.clear()

    def close(self):
        try:
            self.close_cursors()
        finally:
            super().close()


def database_file_identity(path):
    """Include file generation signals as inode numbers can eventually be reused."""
    stat = Path(path).stat()
    return stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns


class SQLiteConnectionPool:
    """Simple SQLite connection pool with shutdown-aware cleanup."""

    def __init__(self, db_path: str, pool_size: int = 10, timeout: float = 30.0,
                 *, readonly_profile: ReadOnlyProfile | None = None):
        if pool_size < 1:
            raise ValueError('pool_size must be positive')
        if readonly_profile is not None:
            if not (1 <= readonly_profile.idle_connections <= readonly_profile.max_connections
                    and readonly_profile.wait_seconds >= 0 and readonly_profile.busy_seconds >= 0
                    and readonly_profile.cache_kib > 0):
                raise ValueError('Invalid read-only pool budget')
            pool_size = readonly_profile.idle_connections
            timeout = readonly_profile.wait_seconds
        self.readonly_profile = readonly_profile
        self._max_connections = readonly_profile.max_connections if readonly_profile else pool_size * 2
        self._file_ids = {}
        self.db_path = str(db_path)
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
            for _ in range(0 if readonly_profile else pool_size):
                self._pool.put(self._create_connection())
        except BaseException:
            self.close_all()
            raise

    def _create_connection(self) -> sqlite3.Connection:
        with self._lock:
            if self._closing:
                raise RuntimeError("Cannot create SQLite connections while the pool is closing")

            identity = self._file_identity() if self.readonly_profile else None
            if self.readonly_profile:
                conn = sqlite3.connect(Path(self.db_path).resolve().as_uri() + '?mode=ro', uri=True,
                                       timeout=self.readonly_profile.busy_seconds, check_same_thread=False,
                                       factory=_ReadOnlyConnection)
            else:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
            try:
                conn.row_factory = sqlite3.Row
                if self.readonly_profile:
                    conn.execute('PRAGMA query_only=ON')
                    conn.execute(f'PRAGMA cache_size=-{self.readonly_profile.cache_kib}')
                    conn.execute('PRAGMA temp_store=FILE')
                else:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
                    conn.execute("PRAGMA cache_size=-16000")
                    conn.execute("PRAGMA temp_store=MEMORY")
            except BaseException:
                conn.close()
                raise
            if self.readonly_profile:
                conn.database_identity = identity
                self._file_ids[conn] = identity
            self._all_conns.add(conn)
            self._created_count = len(self._all_conns)
            return conn

    def _file_identity(self):
        return database_file_identity(self.db_path)

    def _is_current(self, conn):
        try:
            return self._file_ids.get(conn) == self._file_identity()
        except OSError:
            return False

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        deadline = time.monotonic() + self.timeout
        stale_attempts = 0
        while True:
            conn = None
            with self._lock:
                if self._closing:
                    raise RuntimeError(f"SQLite connection pool is closing for {self.db_path}")
                if self.readonly_profile:
                    # Lazy read-only pools grow immediately up to their strict
                    # budget. Waiting never consumes the event-loop thread:
                    # all callers borrow inside their existing sync work.
                    try:
                        conn = self._pool.get_nowait()
                    except Empty:
                        if len(self._all_conns) < self._max_connections:
                            conn = self._create_connection()
            if conn is None:
                # Do not hold the lifecycle lock while waiting for a return.
                try:
                    conn = self._pool.get(timeout=max(0.0, deadline - time.monotonic()))
                except Empty:
                    with self._lock:
                        if self._closing:
                            raise RuntimeError(f"SQLite connection pool is closing for {self.db_path}")
                        try:
                            conn = self._pool.get_nowait()
                        except Empty:
                            if len(self._all_conns) < self._max_connections:
                                conn = self._create_connection()
                            else:
                                raise TimeoutError(
                                    f"Timed out after {self.timeout} seconds waiting for a SQLite connection"
                                )
            with self._lock:
                if self._closing:
                    self._discard_connection(conn)
                    raise RuntimeError(f"SQLite connection pool is closing for {self.db_path}")
                if self.readonly_profile and not self._is_current(conn):
                    self._discard_connection(conn)
                    stale_attempts += 1
                    if stale_attempts > self.pool_size + 1 or (self.timeout > 0 and time.monotonic() > deadline):
                        raise TimeoutError('SQLite database changed during connection acquisition')
                    continue
            break
        try:
            yield conn
        finally:
            self._return_connection(conn)

    def _return_connection(self, conn: sqlite3.Connection) -> None:
        with self._lock:
            if conn not in self._all_conns:
                return  # close_all already closed this checked-out connection.
            if self._closing:
                self._discard_connection(conn)
                return

            try:
                if self.readonly_profile:
                    # Per-request cancellation/tracing must never reach the
                    # next borrower, including interrupted streaming cursors.
                    conn.set_progress_handler(None, 0)
                    conn.set_trace_callback(None)
                    conn.set_authorizer(None)
                    conn.close_cursors()
                    if conn.in_transaction:
                        conn.rollback()
                    if not self._is_current(conn):
                        self._discard_connection(conn)
                        return
                    conn.row_factory = sqlite3.Row
                    conn.execute('PRAGMA query_only=ON')
                conn.execute("SELECT 1")
            except Exception:
                self._discard_connection(conn)
                replacement = None
                try:
                    if not self.readonly_profile and not self._pool.full() and len(self._all_conns) < self._max_connections:
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
                self._file_ids.pop(conn, None)
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

        self._pools: dict[object, SQLiteConnectionPool] = {}
        self._initialized = True

    def get_pool(self, db_path: str, pool_size: int = 10) -> SQLiteConnectionPool:
        if db_path not in self._pools:
            with self._lock:
                if db_path not in self._pools:
                    self._pools[db_path] = SQLiteConnectionPool(db_path, pool_size)
        return self._pools[db_path]

    def get_readonly_pool(self, db_path: str, profile: str) -> SQLiteConnectionPool:
        policy = READONLY_PROFILES[profile]
        path = str(Path(db_path).resolve())
        key = ('readonly', path, profile)
        with self._lock:
            if key not in self._pools:
                self._pools[key] = SQLiteConnectionPool(path, readonly_profile=policy)
            return self._pools[key]

    def close_all(self) -> None:
        with self._lock:
            for pool in self._pools.values():
                pool.close_all()
            self._pools.clear()


db_pool_manager = DatabasePoolManager()


def get_db_pool(db_path: str, pool_size: int = 10) -> SQLiteConnectionPool:
    return db_pool_manager.get_pool(db_path, pool_size)


def close_all_pools() -> None:
    db_pool_manager.close_all()


def get_readonly_db_pool(db_path: str, profile: str) -> SQLiteConnectionPool:
    """Shared lifecycle implementation; separate profiles never borrow writable handles."""
    return db_pool_manager.get_readonly_pool(db_path, profile)
