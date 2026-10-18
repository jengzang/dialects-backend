"""One serial warmup per database across all Web workers."""
import asyncio
import logging
import uuid

from redis.exceptions import RedisError

from .cache import DEFAULTS, _UNLOCK, _wakeups, get_vocabulary_cache

log = logging.getLogger(__name__)


def _load(factory, kind, params):
    from .query import (
        query_vocabulary_items, query_vocabulary_location_options,
        query_vocabulary_map_points, query_vocabulary_standard_words,
    )
    with factory() as session:
        if kind == "sql-count":
            from sqlalchemy import text
            expression = "COUNT(DISTINCT location_name)" if params.get("distinct_column") else "COUNT(*)"
            return {"count": session.execute(text(f"SELECT {expression} FROM vocabulary_entries")).scalar_one()}
        query = {"entries": query_vocabulary_items, "location-options": query_vocabulary_location_options,
                 "map-points": query_vocabulary_map_points, "standard-words": query_vocabulary_standard_words}[kind]
        return query(session=session, **params)


async def warm_once(cache, factory, *, pause=.1):
    token = uuid.uuid4().hex
    lock_key = cache.root + ":warm-lock"
    if not await cache.acquire_lease(lock_key, token):
        return False
    heartbeat = asyncio.create_task(cache.renew_lease(lock_key, token))
    try:
        state = await asyncio.to_thread(cache.state)
        await asyncio.to_thread(cache.cleanup)
        def ready():
            with cache.client.pipeline() as pipe:
                for kind, params in DEFAULTS:
                    pipe.exists(cache.describe(kind, params, state)[0])
                return all(pipe.execute())
        if await asyncio.to_thread(ready):
            return True
        # Compute the 1000-option aggregation once, reuse its first 100 for W4.
        work = [*DEFAULTS[:5], DEFAULTS[6], DEFAULTS[5]]
        large_words = None
        for kind, params in work:
            current = await asyncio.to_thread(cache.state)
            if (current["entries"], current["locations"]) != (state["entries"], state["locations"]):
                return False
            if await asyncio.to_thread(cache.client.get, lock_key) != token:
                return False

            async def load():
                if kind == "standard-words" and params["limit"] == 100 and large_words is not None:
                    return {**large_words, "standard_words": large_words["standard_words"][:100]}
                return await asyncio.to_thread(_load, factory, kind, params)

            result = await cache.acall(kind, params, load, expected_state=state)
            if kind == "standard-words" and params["limit"] == 1000:
                from fastapi.encoders import jsonable_encoder
                large_words = await asyncio.to_thread(jsonable_encoder, result)
            await asyncio.sleep(pause)
        if await asyncio.to_thread(cache.state) != state:
            return False
        log.info("Vocabulary default cache ready for database %s", cache.root)
        return True
    finally:
        heartbeat.cancel()
        await asyncio.gather(heartbeat, return_exceptions=True)
        try:
            await asyncio.to_thread(cache.client.eval, _UNLOCK, 1, lock_key, token)
        except Exception:
            log.warning("Could not release vocabulary warmup lease", exc_info=True)


async def _run(cache, factory, event):
    retry = 0
    while True:
        event.clear()
        try:
            complete = await warm_once(cache, factory)
            retry = 0
            timeout = 60 if complete else 1
        except Exception as exc:
            if isinstance(exc, RedisError):
                cache.failed(exc)
            timeout = (5, 15, 60)[min(retry, 2)]
            retry += 1
            log.warning("Vocabulary warmup failed; retry in %ss", timeout, exc_info=True)
        try:
            await asyncio.wait_for(event.wait(), timeout)
            # Bound the batch window: later notifications do not reset it.
            await asyncio.sleep(1)
        except asyncio.TimeoutError:
            pass


async def start_vocabulary_warmup():
    from app.service.vocabulary.database import SessionLocal
    from app.common.path import VOCABULARY_DB_PATH
    cache = get_vocabulary_cache(VOCABULARY_DB_PATH)
    if cache is None:
        return None
    event = asyncio.Event()
    identity = (asyncio.get_running_loop(), event)
    _wakeups.add(identity)
    # Warm before readiness, while a lease in another worker is awaited asynchronously.
    try:
        while not await warm_once(cache, SessionLocal):
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        _wakeups.discard(identity)
        raise
    except Exception as exc:
        if isinstance(exc, RedisError):
            cache.failed(exc)
        log.warning("Startup warmup deferred until Redis recovers", exc_info=True)
    task = asyncio.create_task(_run(cache, SessionLocal, event), name="vocabulary-cache-warmup")
    return task, identity


async def stop_vocabulary_warmup(handle):
    if handle is None:
        return
    task, identity = handle
    _wakeups.discard(identity)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
