"""Bounded, database-scoped vocabulary cache. No process-local result copies."""
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import threading
import time
import uuid

from fastapi.encoders import jsonable_encoder
from redis.exceptions import RedisError

log = logging.getLogger(__name__)


class CircuitOpen(RedisError):
    """Skipped Redis probe; traffic must not extend the recovery deadline."""

# Only these fixed combinations are permanent, regardless of who computed them.
DEFAULTS = (
    ("sql-count", {}),
    ("sql-count", {"distinct_column": "location_name"}),
    ("location-options", {}),
    ("entries", {}),
    ("map-points", {}),
    ("standard-words", {"limit": 100}),
    ("standard-words", {"limit": 1000}),
)


def normalize(kind, params):
    p = dict(params)
    if kind in {"entries", "map-points", "standard-words", "map-items"}:
        from .query import _normalize_multi_value, _normalize_search_fields
        fields = _normalize_search_fields(p.get("search_fields"))
        p["q"] = (p.get("q") or "").strip()
        p["search_fields"] = sorted(set(fields)) if p["q"] else []
        for field in ("locations", "standard_words"):
            p[field] = sorted(set(_normalize_multi_value(p.get(field))))
        for field in ("province", "city"):
            p[field] = p.get(field) or None
        if kind == "entries":
            p.setdefault("page", 1)
            p.setdefault("page_size", 50)
            if not 1 <= p["page_size"] <= 200 or p["page"] < 1:
                raise ValueError("Invalid vocabulary pagination")
        if kind == "standard-words":
            p.setdefault("limit", 100)
            if p["limit"] is not None and p["limit"] < 1:
                raise ValueError("limit must be at least 1")
        if kind == "map-items" and not p["standard_words"] and not (p.get("standard_word_key") or "").strip():
            raise ValueError("standard_words is required")
    elif kind.startswith("sql-"):
        p.setdefault("table_name", "vocabulary_entries")
        if kind == "sql-count":
            for field in ("distinct_column", "filter_column", "filter_value"):
                p.setdefault(field, None)
            if p["filter_column"] is None:
                p["filter_value"] = None
    return p


def encoded(value):
    return json.dumps(jsonable_encoder(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# Atomic revision check + bounded LRU admission; never evicts a permanent key.
_WRITE = """
if redis.call('HGET', KEYS[1], 'entries') ~= ARGV[1] then return 0 end
if ARGV[2] ~= '' and redis.call('HGET', KEYS[1], 'locations') ~= ARGV[2] then return 0 end
if ARGV[4] == 'default' then redis.call('SET', KEYS[2], ARGV[3]); return 1 end
if string.len(ARGV[3]) > tonumber(ARGV[6]) then return 0 end
local members = redis.call('ZRANGE', KEYS[3], 0, -1)
for _, key in ipairs(members) do
  if redis.call('EXISTS', key) == 0 then redis.call('ZREM', KEYS[3], key) end
end
if redis.call('ZSCORE', KEYS[3], KEYS[2]) == false then
  while redis.call('ZCARD', KEYS[3]) >= tonumber(ARGV[5]) do
    local oldest = redis.call('ZPOPMIN', KEYS[3], 1)
    if string.sub(oldest[1], 1, string.len(ARGV[7])) == ARGV[7] then
      redis.call('UNLINK', oldest[1])
    end
  end
end
local seq = redis.call('INCR', KEYS[4])
redis.call('SET', KEYS[2], ARGV[3], 'EX', 3600)
redis.call('ZADD', KEYS[3], seq, KEYS[2])
return 1
"""
_READ = """
local value = redis.call('GET', KEYS[1])
if value and redis.call('ZSCORE', KEYS[2], KEYS[1]) then
  redis.call('ZADD', KEYS[2], redis.call('INCR', KEYS[3]), KEYS[1])
end
return value
"""
_UNLOCK = "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0"
_RENEW = "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('EXPIRE', KEYS[1], ARGV[2]) end return 0"
_CLEAN = """
if redis.call('HGET', KEYS[1], 'entries') == ARGV[1] and
   (ARGV[2] == '' or redis.call('HGET', KEYS[1], 'locations') == ARGV[2]) then return 0 end
redis.call('UNLINK', KEYS[2])
redis.call('ZREM', KEYS[3], KEYS[2])
return 1
"""


class VocabularyCache:
    def __init__(self, client, db_path, *, namespace="vocabulary", max_keys=128, max_bytes=128 * 1024):
        self.client = client
        self.db_path = str(Path(db_path).resolve())
        self.root = f"{namespace}:{hashlib.md5(self.db_path.encode()).hexdigest()}"
        self.state_key = self.root + ":state"
        self.lru_key = self.root + ":lru"
        self.sequence_key = self.root + ":sequence"
        self.max_keys = max(1, max_keys)
        self.max_bytes = max(1, max_bytes)
        self._retry_at = 0.0
        self._failed = False

    def state(self):
        if time.monotonic() < self._retry_at:
            raise CircuitOpen("Vocabulary Redis circuit open")
        with self.client.pipeline() as pipe:
            pipe.hsetnx(self.state_key, "entries", uuid.uuid4().hex)
            pipe.hsetnx(self.state_key, "locations", uuid.uuid4().hex)
            pipe.hgetall(self.state_key)
            state = pipe.execute()[-1]
        if self._failed:
            # Recovery must not revive values from before a failed invalidation.
            state["entries"] = uuid.uuid4().hex
            self.client.hset(self.state_key, "entries", state["entries"])
            self._failed = False
        return state

    def failed(self, exc):
        if isinstance(exc, CircuitOpen):
            return
        if not self._failed:
            log.warning("Vocabulary Redis unavailable; bypassing cache: %s", exc)
        self._failed = True
        self._retry_at = time.monotonic() + 5

    def describe(self, kind, params, state=None):
        p = normalize(kind, params)
        permanent = any(kind == k and p == normalize(k, v) for k, v in DEFAULTS)
        state = state or self.state()
        scope = "map-points" if kind == "map-points" else "data"
        version = state["entries"]
        if scope == "map-points":
            version += ":" + state["locations"]
        digest = hashlib.md5(encoded(p).encode()).hexdigest()
        mode = "default" if permanent else "ondemand"
        return f"{self.root}:{mode}:{scope}:{version}:{kind}:{digest}", permanent, state

    def key(self, kind, params):
        return self.describe(kind, params)[0]

    def read(self, key):
        value = self.client.eval(_READ, 3, key, self.lru_key, self.sequence_key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            self.client.unlink(key)
            return None

    def store(self, kind, params, value, state):
        key, permanent, _ = self.describe(kind, params, state)
        self.client.eval(_WRITE, 4, self.state_key, key, self.lru_key, self.sequence_key,
                         state["entries"], state["locations"] if kind == "map-points" else "",
                         encoded(value), "default" if permanent else "ondemand",
                         self.max_keys, self.max_bytes, self.root + ":ondemand:")

    def call(self, kind, params, loader):
        """Synchronous caller (service tests/background work); bounded lock wait."""
        try:
            key, _, state = self.describe(kind, params)
            value = self.read(key)
            if value is not None:
                return value
        except RedisError as exc:
            self.failed(exc)
            return loader()
        lock = self.client.lock(self.root + ":compute:" + hashlib.md5(key.encode()).hexdigest(), timeout=120, blocking_timeout=30)
        try:
            if not lock.acquire():
                raise TimeoutError("Vocabulary query is still being prepared")
        except RedisError as exc:
            self.failed(exc)
            return loader()
        try:
            try:
                value = self.read(key)
            except RedisError as exc:
                self.failed(exc)
                return loader()
            if value is not None:
                return value
            value = loader()
            try:
                self.store(kind, params, value, state)
            except RedisError as exc:
                self.failed(exc)
            return value
        finally:
            try:
                lock.release()
            except RedisError:
                log.warning("Vocabulary computation lease expired or Redis disconnected")

    async def acall(self, kind, params, loader, *, expected_state=None):
        """Async wait for shared computation: no thread occupied while polling."""
        try:
            key, _, state = await asyncio.to_thread(self.describe, kind, params, expected_state)
            token = uuid.uuid4().hex
            lock_key = self.root + ":compute:" + hashlib.md5(key.encode()).hexdigest()
            deadline = time.monotonic() + 30
            while True:
                value = await asyncio.to_thread(self.read, key)
                if value is not None:
                    return value
                if await self.acquire_lease(lock_key, token):
                    break
                if time.monotonic() >= deadline:
                    from fastapi import HTTPException
                    raise HTTPException(503, "词表查询正在准备，请稍后重试")
                await asyncio.sleep(.05)
        except RedisError as exc:
            self.failed(exc)
            return await finish_on_cancel(loader())
        heartbeat = asyncio.create_task(self.renew_lease(lock_key, token))
        try:
            # A previous holder may have filled the key between read and SET NX.
            try:
                value = await asyncio.to_thread(self.read, key)
            except RedisError as exc:
                self.failed(exc)
                return await finish_on_cancel(loader())
            if value is not None:
                return value
            value = await finish_on_cancel(loader())
            try:
                await asyncio.to_thread(self.store, kind, params, value, state)
            except RedisError as exc:
                self.failed(exc)
            return value
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            try:
                await asyncio.to_thread(self.client.eval, _UNLOCK, 1, lock_key, token)
            except RedisError:
                pass

    async def acquire_lease(self, key, token):
        """A cancelled SET thread may still acquire; drain it and release by token."""
        try:
            return await finish_on_cancel(asyncio.to_thread(self.client.set, key, token, nx=True, ex=120))
        except asyncio.CancelledError:
            try:
                await asyncio.to_thread(self.client.eval, _UNLOCK, 1, key, token)
            except RedisError:
                log.warning("Redis disconnected while releasing a cancelled lease")
            raise

    async def renew_lease(self, key, token):
        while True:
            await asyncio.sleep(10)
            try:
                if not await asyncio.to_thread(self.client.eval, _RENEW, 1, key, token, 120):
                    return
            except RedisError as exc:
                self.failed(exc)
                return

    def invalidate(self, scope):
        try:
            self.state()
            self.client.hset(self.state_key, "entries" if scope == "entries" else "locations", uuid.uuid4().hex)
        except RedisError as exc:
            self.failed(exc)
        signal_warmup()

    def cleanup(self):
        self.state()
        for mode in ("default", "ondemand"):
            prefix = self.root + ":" + mode + ":"
            for key in self.client.scan_iter(match=prefix + "*", count=32):
                parts = key[len(prefix):].split(":")
                self.client.eval(_CLEAN, 3, self.state_key, key, self.lru_key,
                                 parts[1], parts[2] if parts[0] == "map-points" else "")


_instances = {}
_instances_lock = threading.Lock()
_wakeups = set()


async def finish_on_cancel(awaitable):
    """A cancelled to_thread await does not stop SQLite; keep its lease until done."""
    task = asyncio.create_task(awaitable)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        except Exception:
            log.warning("Vocabulary query failed while draining shutdown", exc_info=True)
        raise


def signal_warmup():
    for loop, event in tuple(_wakeups):
        if not loop.is_closed():
            loop.call_soon_threadsafe(event.set)


def get_vocabulary_cache(db_path):
    from app.common.config import _RUN_TYPE
    if _RUN_TYPE != "WEB":
        return None
    from app.redis_client import sync_redis_client
    path = str(Path(db_path).resolve())
    with _instances_lock:
        if path not in _instances:
            _instances[path] = VocabularyCache(sync_redis_client, path,
                max_keys=int(os.getenv("VOCABULARY_CACHE_MAX_KEYS", "128")),
                max_bytes=int(os.getenv("VOCABULARY_CACHE_MAX_BYTES", str(128 * 1024))))
        return _instances[path]


def notify_vocabulary_change(db_path, *, entries=False, locations=False):
    cache = get_vocabulary_cache(db_path)
    if cache is not None and (entries or locations):
        cache.invalidate("entries" if entries else "locations")


async def cached_search(kind, session, query, **params):
    # Validate even on a hit. A cache must not hide invalid search fields.
    normalize(kind, params)
    cache = get_vocabulary_cache(session.get_bind().url.database)
    async def load():
        return await asyncio.to_thread(query, session=session, **params)
    return await cache.acall(kind, params, load) if cache else await finish_on_cancel(load())


async def cached_sql(db_path, kind, params, query, *args, **kwargs):
    cache = get_vocabulary_cache(db_path)
    async def load():
        return await asyncio.to_thread(query, *args, **kwargs)
    return await cache.acall(kind, params, load) if cache else await finish_on_cancel(load())


def count_changed_values(cursor, table, where, values, updates):
    """SQLite IS NOT respects column affinity and also compares NULL safely.

    Identifiers are already validated by the calling write endpoint.
    """
    if not updates:
        return 0
    # SQLite legacy SELECT does not begin a transaction. Hold a write reservation
    # until the following UPDATE so a concurrent writer cannot turn a no-op
    # snapshot into a real mutation without cache invalidation.
    if not cursor.connection.in_transaction:
        cursor.execute("BEGIN IMMEDIATE")
    condition = " OR ".join(f'"{col}" IS NOT ?' for col in updates)
    return cursor.execute(f'SELECT COUNT(*) FROM "{table}" WHERE ({where}) AND ({condition})',
                          [*values, *updates.values()]).fetchone()[0]
