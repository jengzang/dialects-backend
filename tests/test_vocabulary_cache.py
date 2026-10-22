"""Real Redis integration tests; only this run's namespace is removed."""
import concurrent.futures
import os
import threading
import time
import uuid

import pytest
import redis


def test_open_circuit_traffic_does_not_postpone_recovery(cache, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(time, 'monotonic', lambda: now[0])
    cache.failed(redis.ConnectionError('outage'))
    now[0] = 104
    assert cache.call('entries', {}, lambda: {'fallback': True}) == {'fallback': True}
    assert cache._retry_at == 105
    now[0] = 106
    cache.call('entries', {}, lambda: {'recovered': True})
    assert cache.read(cache.key('entries', {})) == {'recovered': True}


def test_warmup_reused_words_cannot_publish_into_new_revision(cache, monkeypatch):
    import asyncio
    from app.service.vocabulary import cache_warmup
    async_call = cache.acall
    switched = False
    async def injected(kind, params, loader, **kwargs):
        nonlocal switched
        if kind == 'standard-words' and params['limit'] == 100:
            switched = True
            cache.invalidate('entries')
        return await async_call(kind, params, loader, **kwargs)
    monkeypatch.setattr(cache, 'acall', injected)
    monkeypatch.setattr(cache_warmup, '_load', lambda *args: {'standard_words': ['OLD']})
    assert asyncio.run(cache_warmup.warm_once(cache, None, pause=0)) is False
    assert switched
    assert cache.read(cache.key('standard-words', {'limit': 100})) is None


@pytest.fixture
def cache(tmp_path):
    from app.service.vocabulary.cache import VocabularyCache

    client = redis.Redis.from_url(os.environ.get("VOCABULARY_TEST_REDIS_URL", "redis://127.0.0.1:16379/0"), decode_responses=True)
    try:
        client.ping()
    except redis.ConnectionError:
        if os.environ.get("VOCABULARY_TEST_REDIS_URL"):
            raise
        pytest.skip("Set VOCABULARY_TEST_REDIS_URL to run the real Redis integration tests")
    instance = VocabularyCache(client, str(tmp_path / "vocabulary.db"), namespace="vocabulary-test-" + uuid.uuid4().hex, max_keys=2, max_bytes=128)
    yield instance
    keys = list(client.scan_iter(match=instance.root + ":*"))
    if keys:
        client.unlink(*keys)
    client.close()


def test_defaults_permanent_and_equivalent_empty_parameters(cache):
    first = cache.call("entries", {}, lambda: {"items": [], "total": 0})
    second = cache.call("entries", {"q": "  ", "page": 1, "page_size": 50, "search_fields": ["definition"]}, lambda: pytest.fail("cache miss"))
    assert first == second
    assert cache.client.ttl(cache.key("entries", {})) == -1


def test_lru_replaces_demand_only_and_does_not_extend_ttl(cache):
    cache.call("map-points", {}, lambda: {"points": []})
    for q in ["a", "b"]:
        cache.call("entries", {"q": q}, lambda: {"items": []})
    a = cache.key("entries", {"q": "a"})
    b = cache.key("entries", {"q": "b"})
    cache.client.expire(a, 30)
    cache.call("entries", {"q": "a"}, lambda: pytest.fail("cache miss"))
    cache.call("entries", {"q": "c"}, lambda: {"items": []})
    assert cache.client.exists(a)
    assert not cache.client.exists(b)
    assert 0 < cache.client.ttl(a) <= 30
    assert 3500 < cache.client.ttl(cache.key("entries", {"q": "c"})) <= 3600
    assert cache.client.ttl(cache.key("map-points", {})) == -1
    assert cache.client.zcard(cache.lru_key) == 2


def test_expired_and_oversized_entries_do_not_evict_live_values(cache):
    cache.call("entries", {"q": "a"}, lambda: {})
    a = cache.key("entries", {"q": "a"})
    cache.call("entries", {"q": "large"}, lambda: {"data": "x" * 129})
    assert cache.client.exists(a)
    assert not cache.client.exists(cache.key("entries", {"q": "large"}))
    cache.client.delete(a)
    cache.call("entries", {"q": "b"}, lambda: {})
    assert cache.client.zcard(cache.lru_key) == 1


def test_locations_invalidate_map_only_entries_invalidate_everything(cache):
    for kind in ["entries", "location-options", "map-points", "map-items", "standard-words", "sql-query", "sql-count", "sql-distinct"]:
        cache.call(kind, {"standard_words": ["太阳"]} if kind == "map-items" else {}, lambda: {"old": True})
    old_map = cache.key("map-points", {})
    old_entry = cache.key("entries", {})
    cache.invalidate("locations")
    assert cache.key("entries", {}) == old_entry
    assert cache.key("map-points", {}) != old_map
    assert cache.client.exists(old_entry)
    cache.invalidate("entries")
    assert cache.key("entries", {}) != old_entry
    cache.cleanup()
    assert not cache.client.exists(old_entry)
    assert not cache.client.exists(old_map)


def test_concurrent_miss_computes_once(cache):
    count = 0
    def load():
        nonlocal count
        count += 1
        time.sleep(.1)
        return {"value": count}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: cache.call("entries", {}, load), range(4)))
    assert count == 1
    assert results == [{"value": 1}] * 4


def test_invalidation_during_query_cannot_resurrect_old_data(cache):
    old = cache.key("entries", {})
    def load():
        cache.invalidate("entries")
        return {"old": True}
    assert cache.call("entries", {}, load) == {"old": True}
    assert not cache.client.exists(old)
    assert not cache.client.exists(cache.key("entries", {}))


def test_concurrent_admission_stays_bounded(cache):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: cache.call("entries", {"q": str(n)}, lambda: {}), range(20)))
    assert cache.client.zcard(cache.lru_key) == 2
    assert len(list(cache.client.scan_iter(match=cache.root + ":ondemand:*"))) == 2


def test_warmup_populates_seven_permanent_results_and_refreshes_only_map(cache, tmp_path):
    from app.service.vocabulary.cache_warmup import warm_once
    from app.service.vocabulary.database import create_vocabulary_engine_and_session
    from app.service.vocabulary.models import Base, VocabularyEntry, VocabularyLocation
    import asyncio

    engine, factory = create_vocabulary_engine_and_session(cache.db_path)
    Base.metadata.create_all(engine)
    with factory() as session:
        session.add(VocabularyLocation(user_id=1, location_name="甲", coordinates="106,27"))
        session.add(VocabularyEntry(user_id=1, location_name="甲", standard_word="太阳", local_expression="日头", ipa="a"))
        session.commit()
    asyncio.run(warm_once(cache, factory, pause=0))
    from app.service.vocabulary.cache import DEFAULTS
    assert [cache.client.ttl(cache.key(k, p)) for k, p in DEFAULTS] == [-1] * 7
    assert cache.read(cache.key("sql-count", {})) == {"count": 1}
    assert cache.read(cache.key("map-points", {}))["points"][0]["longitude"] == 106
    entry_key = cache.key("entries", {})
    with factory() as session:
        session.query(VocabularyLocation).update({"coordinates": "107,28"})
        session.commit()
    cache.invalidate("locations")
    asyncio.run(warm_once(cache, factory, pause=0))
    assert cache.key("entries", {}) == entry_key
    assert cache.read(cache.key("map-points", {}))["points"][0]["longitude"] == 107
    with factory() as session:
        session.add(VocabularyEntry(user_id=1, location_name="甲", standard_word="月亮", local_expression="月光", ipa="b"))
        session.commit()
    cache.invalidate("entries")
    asyncio.run(warm_once(cache, factory, pause=0))
    assert cache.read(cache.key("sql-count", {})) == {"count": 2}
    assert cache.read(cache.key("map-points", {}))["total_entries"] == 2
    assert not cache.client.exists(entry_key)
    engine.dispose()


def test_warmup_global_lease_serializes_versions(cache):
    from app.service.vocabulary.cache_warmup import warm_once
    import asyncio
    cache.client.set(cache.root + ":warm-lock", "other-worker", ex=30)
    assert asyncio.run(warm_once(cache, lambda: pytest.fail("must not query"), pause=0)) is False


@pytest.mark.parametrize('warmup', [False, True])
def test_cancel_during_redis_lock_acquisition_does_not_leave_lease(cache, monkeypatch, warmup):
    import asyncio
    from app.service.vocabulary.cache_warmup import warm_once
    entered = threading.Event()
    release = threading.Event()
    original_set = cache.client.set
    def slow_set(*args, **kwargs):
        entered.set()
        release.wait(5)
        return original_set(*args, **kwargs)
    monkeypatch.setattr(cache.client, 'set', slow_set)
    async def unexpected():
        pytest.fail('cancelled request must not compute')
    async def scenario():
        task = asyncio.create_task(warm_once(cache, None) if warmup else cache.acall('entries', {}, unexpected))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            task.cancel()
            await asyncio.sleep(.02)
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            # Ensure the Redis thread has finished before inspecting leases.
            await asyncio.sleep(.02)
            assert not list(cache.client.scan_iter(match=cache.root + ':compute:*'))
            assert not cache.client.exists(cache.root + ':warm-lock')
        finally:
            release.set()
    asyncio.run(scenario())


def test_async_requests_share_computation_and_drain_cancel_before_unlock(cache):
    import asyncio
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        loads = 0
        async def load():
            nonlocal loads
            loads += 1
            entered.set()
            await release.wait()
            return {"ok": True}
        first = asyncio.create_task(cache.acall("entries", {}, load))
        await entered.wait()
        first.cancel()
        await asyncio.sleep(.03)
        assert not first.done()
        second = asyncio.create_task(cache.acall("entries", {}, load))
        await asyncio.sleep(.03)
        assert loads == 1
        release.set()
        await asyncio.gather(first, return_exceptions=True)
        assert await second == {"ok": True}
        # The cancelled owner drains but does not publish its incomplete response;
        # the next owner performs the one subsequent computation.
        assert loads == 2
    asyncio.run(scenario())


def test_redis_failure_falls_back_and_recovery_rejects_previous_values(cache, monkeypatch):
    cache.call("entries", {}, lambda: {"old": True})
    old = cache.key("entries", {})
    original_eval = cache.client.eval
    monkeypatch.setattr(cache.client, "eval", lambda *args, **kwargs: (_ for _ in ()).throw(redis.ConnectionError("test outage")))
    assert cache.call("entries", {}, lambda: {"new": True}) == {"new": True}
    cache.invalidate("entries")  # failed version switch is recovered on next health check
    monkeypatch.setattr(cache.client, "eval", original_eval)
    cache._retry_at = 0
    assert cache.key("entries", {}) != old
    assert cache.call("entries", {}, lambda: {"new": True}) == {"new": True}


def test_stale_cleanup_cannot_remove_current_values(cache):
    from app.service.vocabulary.cache import _CLEAN
    cache.call("entries", {}, lambda: {"current": True})
    key = cache.key("entries", {})
    state = cache.state()
    assert cache.client.eval(_CLEAN, 3, cache.state_key, key, cache.lru_key, state["entries"], "") == 0
    assert cache.client.exists(key)


def test_default_missing_key_is_actively_repaired_after_write(cache, tmp_path):
    import asyncio
    from sqlalchemy import text
    from app.service.vocabulary.cache import DEFAULTS, _wakeups
    from app.service.vocabulary.cache_warmup import _run, warm_once
    from app.service.vocabulary.database import create_vocabulary_engine_and_session
    from app.service.vocabulary.models import Base
    engine, factory = create_vocabulary_engine_and_session(cache.db_path)
    Base.metadata.create_all(engine)
    async def scenario():
        await warm_once(cache, factory, pause=0)
        event = asyncio.Event()
        identity = (asyncio.get_running_loop(), event)
        _wakeups.add(identity)
        task = asyncio.create_task(_run(cache, factory, event))
        try:
            # Let the initial health pass finish, then commit a change without any HTTP reads.
            await asyncio.sleep(1)
            with factory() as session:
                session.execute(text("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES (1,'甲','日','日','a')"))
                session.commit()
            cache.invalidate("entries")
            for _ in range(60):
                await asyncio.sleep(.1)
                if all(cache.client.exists(cache.key(k, p)) for k, p in DEFAULTS):
                    break
            assert [cache.client.ttl(cache.key(k, p)) for k, p in DEFAULTS] == [-1] * 7
            assert cache.read(cache.key("sql-count", {})) == {"count": 1}
        finally:
            _wakeups.discard(identity)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())
    engine.dispose()
