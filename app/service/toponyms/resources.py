"""Bounded SQLite work for the single-host toponyms service."""
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from .config import QUERY_TIMEOUT_SECONDS


class QueryBusy(Exception):
    pass


class QueryTimedOut(Exception):
    pass


class QueryTooBroad(Exception):
    pass


_deadline = ContextVar("toponyms_deadline", default=None)


def check_deadline():
    deadline = _deadline.get()
    if deadline is not None and time.monotonic() >= deadline:
        raise QueryTimedOut("Toponym query exceeded its execution budget")


@contextmanager
def connection(path, timeout=QUERY_TIMEOUT_SECONDS):
    """No WAL changes, pooled caches or surviving queries after close."""
    deadline = _deadline.get()
    if timeout is not None:
        deadline = min(deadline, time.monotonic() + timeout) if deadline else time.monotonic() + timeout
    token = _deadline.set(deadline)
    conn = None
    try:
        conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=0.1)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA cache_size=-4096")
        conn.execute("PRAGMA temp_store=FILE")
        conn.set_progress_handler(lambda: deadline is not None and time.monotonic() >= deadline, 1000)
        check_deadline()
        yield conn
        check_deadline()
    except sqlite3.OperationalError as exc:
        if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT:
            raise QueryTimedOut("Toponym SQL exceeded its execution budget") from exc
        raise
    finally:
        if conn is not None:
            conn.set_progress_handler(None, 0)
            conn.close()
        _deadline.reset(token)


@contextmanager
def _slot(path, category, count):
    # flock is shared by independent Gunicorn workers and released on process exit.
    # Never unlink lock files: replacing their inode would defeat mutual exclusion.
    import fcntl

    root = Path(os.environ.get("TOPONYMS_LOCK_DIR", str(Path(tempfile.gettempdir()) / "dialects-toponyms-locks")))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    identity = hashlib.sha256(os.path.realpath(path).encode()).hexdigest()[:24]
    acquired = None
    try:
        for index in range(count):
            fd = os.open(root / f"{identity}-{category}-{index}.lock", os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                continue
            except BaseException:
                os.close(fd)
                raise
            acquired = fd
            break
        if acquired is None:
            raise QueryBusy("Toponym execution slots are occupied")
        yield
    finally:
        if acquired is not None:
            os.close(acquired)


@contextmanager
def execution_slot(path, category):
    with ExitStack() as stack:
        if category == "tree":
            stack.enter_context(_slot(path, "tree", 1))
        stack.enter_context(_slot(path, "light" if category == "light" else "heavy",
                                  1 if category == "light" else 2))
        yield
