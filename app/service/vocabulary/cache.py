"""Bounded, database-scoped vocabulary cache. No process-local result copies."""
import asyncio
from dataclasses import fields, is_dataclass
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

SEARCH_KINDS = frozenset({'entries-count', 'entries', 'map-points', 'standard-words', 'map-items',
                          'location-options', 'partition-options'})


def normalize(kind, params):
    p = dict(params)
    if kind in SEARCH_KINDS:
        from .partitions import normalize_regions
        region_mode = p.get('region_mode', 'yindian')
        if kind == 'partition-options':
            p.setdefault('parent', None)
            normalize_regions([p['parent']] if p['parent'] is not None else None, region_mode)
            p['region_mode'] = region_mode
        else:
            p['regions'] = normalize_regions(p.get('regions'), region_mode)
            p['region_mode'] = region_mode if p['regions'] else 'yindian'
            for field in ('province', 'city'):
                p[field] = p.get(field) or None
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


def bounded_encoded(value, maximum):
    """Encode optional cache data without first copying a complete result.

    Only the plain JSON/dataclass shapes used by vocabulary queries are handled.
    Other shapes skip this optional cache, rather than changing serialization
    semantics. Permanent defaults continue through the original encoder.
    Object key order is internal to Redis; response values/order are untouched.
    """
    def tokens(item, depth=0):
        if depth > 64:
            raise ValueError('Cache value is too deeply nested')
        if type(item) is str:
            if len(item) <= 1024:
                yield json.dumps(item, ensure_ascii=False)
                return
            yield '"'
            # iterencode alone still allocates an entire escaped large string.
            for offset in range(0, len(item), 1024):
                yield json.dumps(item[offset:offset + 1024], ensure_ascii=False)[1:-1]
            yield '"'
        elif item is None or type(item) in (bool, int, float):
            yield json.dumps(item)
        elif type(item) in (list, tuple):
            yield '['
            for index, child in enumerate(item):
                if index:
                    yield ','
                yield from tokens(child, depth + 1)
            yield ']'
        elif type(item) is dict or (is_dataclass(item) and not isinstance(item, type)):
            pairs = item.items() if type(item) is dict else (
                (field.name, getattr(item, field.name)) for field in fields(item))
            yield '{'
            first = True
            for key, child in pairs:
                if type(key) is not str:
                    raise ValueError('Unsupported cache key')
                if key.startswith('_sa'):
                    continue  # Match jsonable_encoder's sqlalchemy_safe default.
                if not first:
                    yield ','
                first = False
                yield from tokens(key, depth + 1)
                yield ':'
                yield from tokens(child, depth + 1)
            yield '}'
        else:
            raise ValueError('Unsupported optional cache value')

    chunks, size = [], 0
    try:
        for chunk in tokens(value):
            size += len(chunk.encode('utf-8'))
            if size > maximum:
                return None
            chunks.append(chunk)
    except (ValueError, UnicodeError, RecursionError):
        return None
    return ''.join(chunks)


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
_CLEANUP_COMMIT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
redis.call('HSET', KEYS[2], 'default', ARGV[2], 'ondemand', ARGV[3], 'pending', ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[5])
return 1
"""
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
        # New scope also prevents serving pre-partition response schemas after deployment.
        scope = "search-v2" if kind in SEARCH_KINDS else "data"
        version = state["entries"]
        if kind in SEARCH_KINDS:
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
        payload = encoded(value) if permanent else bounded_encoded(value, self.max_bytes)
        if payload is None:
            return
        self.client.eval(_WRITE, 4, self.state_key, key, self.lru_key, self.sequence_key,
                         state["entries"], state["locations"] if kind in SEARCH_KINDS else "",
                         payload, "default" if permanent else "ondemand",
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

    async def acall(self, kind, params, loader, *, expected_state=None, wait_for_lease=True):
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
                if not wait_for_lease:
                    from .resources import BackgroundBusy
                    raise BackgroundBusy()
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
            with self.client.pipeline() as pipe:
                pipe.hset(self.state_key, "entries" if scope == "entries" else "locations", uuid.uuid4().hex)
                # A new revision may advance cleanup without waiting for the idle cooldown.
                pipe.delete(self.root + ':cleanup-gate')
                pipe.execute()
        except RedisError as exc:
            self.failed(exc)
        signal_warmup()

    def cleanup(self):
        """Advance at most one SCAN page per mode under the warmup lease.

        Redis owns the cursors/cooldown, shared by workers. COUNT is a hint;
        only a page is held, never a complete keyspace list. Old keys are
        removed with the existing atomic revision check before cursor commit.
        """
        gate = self.root + ':cleanup-gate'
        progress = self.root + ':cleanup-progress'
        token = uuid.uuid4().hex
        if not self.client.set(gate, token, nx=True, ex=60):
            self._cleanup_pending = self.client.hget(progress, 'pending') == '1'
            return self._cleanup_pending
        try:
            return self._cleanup_page(gate, progress, token)
        except Exception:
            try:
                self.client.eval(_UNLOCK, 1, gate, token)
            except RedisError:
                log.warning('Could not release vocabulary cleanup gate', exc_info=True)
            raise

    def _cleanup_page(self, gate, progress, token):
        self.state()
        cursors = self.client.hgetall(progress)
        updated = {}
        for mode in ("default", "ondemand"):
            cursor = cursors.get(mode, '0')
            if cursor == '-1':
                updated[mode] = '-1'
                continue
            prefix = self.root + ":" + mode + ":"
            next_cursor, keys = self.client.scan(cursor=int(cursor), match=prefix + '*', count=32)
            with self.client.pipeline(transaction=False) as pipe:
                for key in keys:
                    parts = key[len(prefix):].split(':')
                    if len(parts) < 4:
                        continue
                    if parts[0] != 'search-v2' and parts[-2] in SEARCH_KINDS:
                        pipe.unlink(key)
                        pipe.zrem(self.lru_key, key)
                    else:
                        pipe.eval(_CLEAN, 3, self.state_key, key, self.lru_key,
                                  parts[1], parts[2] if parts[0] == 'search-v2' else '')
                pipe.execute()
            updated[mode] = str(next_cursor) if next_cursor else '-1'
        pending = any(cursor != '-1' for cursor in updated.values())
        if not pending:
            updated = {'default': '0', 'ondemand': '0'}
        updated['pending'] = '1' if pending else '0'
        # A failed page may safely repeat; never commit a cursor before deletion.
        committed = self.client.eval(_CLEANUP_COMMIT, 2, gate, progress, token,
                                     updated['default'], updated['ondemand'], updated['pending'],
                                     1 if pending else 60)
        self._cleanup_pending = pending or not committed
        return self._cleanup_pending


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
    def run():
        if kind == "entries" and cache is not None:
            def count(sql, values):
                def execute():
                    cursor = session.connection().connection.cursor()
                    try:
                        return cursor.execute(sql, values).fetchone()[0]
                    finally:
                        cursor.close()
                return cache.call("entries-count", {"sql": sql, "values": values}, execute)
            return query(session=session, _count_loader=count, **params)
        return query(session=session, **params)
    async def load():
        from .resources import run_bounded
        return await run_bounded(session.get_bind().url.database, run, expensive=kind in {"standard-words", "map-items"})
    return await cache.acall(kind, params, load) if cache else await finish_on_cancel(load())



async def cached_sql(db_path, kind, params, query, *args, **kwargs):
    cache = get_vocabulary_cache(db_path)
    async def load():
        from .resources import run_bounded
        return await run_bounded(db_path, query, *args, **kwargs)
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
