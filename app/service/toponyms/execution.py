"""Small process-local cache and bounded single-flight request execution."""
import asyncio
from collections import OrderedDict
from concurrent.futures import Future
import hashlib
import json
import logging
import os
import threading
import time

from starlette.concurrency import run_in_threadpool
from .resources import execution_slot, QueryBusy

logger = logging.getLogger(__name__)


class ResultCache:
    def __init__(self, max_bytes=4 * 1024 * 1024, max_entries=256, max_item_bytes=128 * 1024):
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self.max_item_bytes = max_item_bytes
        self.entries = OrderedDict()
        self.size = 0
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            entry = self.entries.get(key)
            if entry is None:
                return None
            expires, value = entry
            if expires <= time.monotonic():
                self.entries.pop(key)
                self.size -= len(value)
                return None
            self.entries.move_to_end(key)
            return value

    def put(self, key, value, ttl):
        if len(value) > min(self.max_item_bytes, self.max_bytes):
            return
        with self.lock:
            old = self.entries.pop(key, None)
            if old:
                self.size -= len(old[1])
            self.entries[key] = (time.monotonic() + ttl, value)
            self.size += len(value)
            while self.size > self.max_bytes or len(self.entries) > self.max_entries:
                _, (_, removed) = self.entries.popitem(last=False)
                self.size -= len(removed)


_cache = ResultCache()
_flights = {}
_tasks = set()
_lock = threading.Lock()
_waiters = 0
MAX_FLIGHTS = 4
MAX_WAITERS = 8


def _version(path):
    stamps = []
    for name in (path, path + "-wal"):
        try:
            stat = os.stat(name)
            stamps.append((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        except FileNotFoundError:
            stamps.append(None)
    return stamps


def _compute(func, path, category, kwargs):
    start = time.monotonic()
    try:
        with execution_slot(path, category):
            result = func(**kwargs)
            # Encoding occurs in the worker; only small payloads enter the cache.
            payload = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()
            return result, payload
    finally:
        logger.info("toponyms query=%s category=%s elapsed_ms=%.1f",
                    func.__name__, category, (time.monotonic() - start) * 1000)


async def _produce(key, future, func, path, category, kwargs):
    try:
        result, payload = await run_in_threadpool(_compute, func, path, category, kwargs)
        # All results have a short TTL; DB/WAL changes also invalidate the key.
        _cache.put(key, payload, 30)
        future.set_result(result)
    except BaseException as exc:
        future.set_exception(exc)
    finally:
        with _lock:
            _flights.pop(key, None)


async def run_query(func, *, db_path=None, **kwargs):
    global _waiters
    if db_path is None:
        from . import repository
        db_path = repository.TOPONYMS_DB_PATH
    path = os.path.realpath(db_path)
    category = ("tree" if func.__name__ == "list_names_with_division_tree"
                else "light" if func.__name__ in {"list_details_by_ids", "list_child_divisions"}
                else "heavy")
    normalized = dict(kwargs)
    if "place_type_codes" in normalized and normalized["place_type_codes"] is not None:
        normalized["place_type_codes"] = sorted(set(normalized["place_type_codes"]))
    key = hashlib.sha256(json.dumps(
        [path, _version(path), func.__module__, func.__qualname__, normalized],
        sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()
    cached = _cache.get(key)
    if cached is not None:
        return await run_in_threadpool(json.loads, cached)
    with _lock:
        if _waiters >= MAX_WAITERS:
            raise QueryBusy("Too many toponym request waiters")
        future = _flights.get(key)
        if future is None:
            if len(_flights) >= MAX_FLIGHTS:
                raise QueryBusy("Too many pending toponym queries")
            future = Future()
            _flights[key] = future
            task = asyncio.create_task(_produce(key, future, func, path, category, normalized))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
        _waiters += 1
    try:
        # A disconnected follower must not cancel another request's SQL or
        # release its slot. The producer owns the slot until actual completion.
        return await asyncio.shield(asyncio.wrap_future(future))
    finally:
        with _lock:
            _waiters -= 1
