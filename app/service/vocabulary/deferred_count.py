"""Optional totals: send a bounded page, then attempt one same-worker count.

No queue or new executor. Cross-worker leases and existing resource slots bound
background SQL. A lost/failed/skipped task never prevents has_more pagination.
"""
import asyncio
import hashlib
import logging
import time
import uuid

from redis.exceptions import RedisError
from sqlalchemy.orm import sessionmaker

from . import cache as cache_module
from .cache import _UNLOCK, finish_on_cancel
from .query import query_vocabulary_items
from .resources import BackgroundBusy, run_bounded

log = logging.getLogger(__name__)
COUNT_SECONDS = 5
LEASE_SECONDS = 120
COOLDOWN_SECONDS = 15


def _same_revision(first, second):
    return (first['entries'], first['locations']) == (second['entries'], second['locations'])


async def cached_deferred_entries(session, background_tasks, **params):
    """Keep legacy callers exact; only opted-in HTTP requests use this path."""
    cache_module.normalize('entries', params)
    path = session.get_bind().url.database
    cache = cache_module.get_vocabulary_cache(path)
    state = None
    if cache is not None:
        try:
            state = await asyncio.to_thread(cache.state)
            # Existing default prewarm and exact-mode pages already contain
            # everything needed. Preserve their zero-SQL hit path as well.
            legacy_key = cache.describe('entries', params, state)[0]
            legacy = await asyncio.to_thread(cache.read, legacy_key)
            if legacy is not None and legacy.get('total') is not None:
                return {**legacy, 'has_more':
                        params.get('page', 1) * params.get('page_size', 50) < legacy['total']}
        except RedisError as exc:
            cache.failed(exc)
            state = None
    request_params = {**params, 'defer_total': True}

    def query():
        signature = None
        cached_total = None
        def count(sql, values, execute):
            nonlocal signature, cached_total
            signature = {'sql': sql, 'values': values}
            if cache is not None and state is not None:
                try:
                    key = cache.describe('entries-count', signature, state)[0]
                    cached_total = cache.read(key)
                except RedisError as exc:
                    cache.failed(exc)
            return cached_total
        result = query_vocabulary_items(session=session, _count_resolver=count, **request_params)
        if result.total is not None and cached_total is None and cache is not None and state is not None:
            try:
                cache.store('entries-count', signature, result.total, state)
            except RedisError as exc:
                cache.failed(exc)
        return result

    async def load():
        return await run_bounded(path, query)
    if cache is not None and state is not None:
        result = await cache.acall('entries', request_params, load, expected_state=state)
    else:
        result = await finish_on_cancel(load())
    total = result.get('total') if isinstance(result, dict) else result.total
    if total is None and cache is not None and state is not None:
        # Capture only the engine/factory, never the request's Session/connection.
        factory = sessionmaker(bind=session.get_bind(), autoflush=False)
        background_tasks.add_task(complete_count, cache, factory, dict(params), state)
    return result


async def complete_count(cache, factory, params, state):
    """One non-waiting attempt after the response body; no automatic retries."""
    token = uuid.uuid4().hex
    active = cache.root + ':count-active'
    cooldown = cache.root + ':count-cooldown'
    acquired = False
    try:
        def eligible():
            return _same_revision(cache.state(), state) and not cache.client.exists(cooldown)
        if not await asyncio.to_thread(eligible):
            return
        # Reuse cancellation-safe SET NX: a cancelled Redis thread may still
        # acquire, so it must be drained and unlocked by token before exit.
        acquired = await cache.acquire_lease(active, token)
        if not acquired:
            return

        def count():
            with factory() as session:
                conn = session.connection().connection
                previous_busy = conn.execute('PRAGMA busy_timeout').fetchone()[0]
                deadline = time.monotonic() + COUNT_SECONDS
                # progress callbacks do not fire during SQLite lock waits.
                conn.execute('PRAGMA busy_timeout=100')
                conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10000)
                def resolve(sql, values, execute):
                    if not _same_revision(cache.state(), state):
                        raise BackgroundBusy()
                    signature = {'sql': sql, 'values': values}
                    key = cache.describe('entries-count', signature, state)[0]
                    existing = cache.read(key)
                    if existing is not None:
                        return existing
                    # Share the legacy synchronous count computation lock.
                    lock = cache.root + ':compute:' + hashlib.md5(key.encode()).hexdigest()
                    if not cache.client.set(lock, token, nx=True, ex=LEASE_SECONDS):
                        raise BackgroundBusy()
                    try:
                        existing = cache.read(key)
                        if existing is not None:
                            return existing
                        total = execute()
                        cache.store('entries-count', signature, total, state)
                        return total
                    finally:
                        cache.client.eval(_UNLOCK, 1, lock, token)
                try:
                    query_vocabulary_items(session=session, _count_resolver=resolve,
                                           _count_only=True, **params)
                finally:
                    conn.set_progress_handler(None, 0)
                    conn.execute(f'PRAGMA busy_timeout={int(previous_busy)}')

        await run_bounded(cache.db_path, count, background=True, expensive=True)
    except BackgroundBusy:
        pass
    except Exception as exc:
        if isinstance(exc, RedisError):
            cache.failed(exc)
        log.warning('Deferred vocabulary count skipped after failure: %s', exc)
        try:
            await asyncio.to_thread(cache.client.set, cooldown, '1', ex=COOLDOWN_SECONDS)
        except RedisError:
            pass
    finally:
        if acquired:
            try:
                await asyncio.to_thread(cache.client.eval, _UNLOCK, 1, active, token)
            except RedisError:
                pass  # Worker loss/Redis outage leaves only an expiring lease.
