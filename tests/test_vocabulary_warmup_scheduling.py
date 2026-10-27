"""Warmup scheduling with real isolated Redis and unchanged default payloads."""
import asyncio
from contextlib import contextmanager
import threading

import pytest

from app.service.vocabulary import cache_warmup, resources
from app.service.vocabulary.cache import DEFAULTS, VocabularyCache
from tests.test_vocabulary_cache import cache


@pytest.fixture
def pause_calls(monkeypatch):
    original = asyncio.sleep
    calls = []
    async def sleep(seconds):
        if seconds == .12345:
            calls.append(seconds)
            await original(0)
        else:
            await original(seconds)
    monkeypatch.setattr(asyncio, 'sleep', sleep)
    return calls


def populate(cache):
    state = cache.state()
    for kind, params in DEFAULTS:
        value = {'kind': kind}
        if kind == 'standard-words':
            value = {'standard_words': list(range(params['limit'])), 'total': 5678}
        cache.store(kind, params, value, state)


def test_only_missing_map_has_no_pause(cache, monkeypatch, pause_calls):
    populate(cache)
    cache.client.delete(cache.key('map-points', {}))
    calls = []
    def load(factory, kind, params):
        calls.append(kind)
        return {'kind': kind}
    monkeypatch.setattr(cache_warmup, '_load', load)
    assert asyncio.run(cache_warmup.warm_once(cache, None, pause=.12345))
    assert calls == ['map-points']
    assert pause_calls == []


def test_cold_warmup_waits_only_between_real_queries(cache, monkeypatch, pause_calls):
    calls = []
    def load(factory, kind, params):
        calls.append((kind, params))
        if kind == 'standard-words':
            return {'standard_words': list(range(1000)), 'total': 5678}
        return {'kind': kind}
    monkeypatch.setattr(cache_warmup, '_load', load)
    assert asyncio.run(cache_warmup.warm_once(cache, None, pause=.12345))
    assert len(calls) == 8
    assert len(pause_calls) == 7
    assert cache.read(cache.key('standard-words', {'limit': 1000})) == {
        'standard_words': list(range(1000)), 'total': 5678}
    assert cache.read(cache.key('standard-words', {'limit': 100})) is None


def test_small_word_list_is_demand_only_without_proactive_query_or_pause(cache, monkeypatch, pause_calls):
    populate(cache)
    monkeypatch.setattr(cache_warmup, '_load', lambda *args: pytest.fail('aggregation repeated'))
    assert asyncio.run(cache_warmup.warm_once(cache, None, pause=.12345))
    assert cache.read(cache.key('standard-words', {'limit': 100})) is None
    assert not cache.describe('standard-words', {'limit': 100})[1]
    assert len(DEFAULTS) == 8
    cache.call('standard-words', {'limit': 100}, lambda: {'standard_words': [], 'total': 0})
    assert 0 < cache.client.ttl(cache.key('standard-words', {'limit': 100})) <= 3600
    assert cache.client.ttl(cache.key('standard-words', {'limit': 1000})) == -1
    assert pause_calls == []


def test_warmup_cleans_after_filling_defaults(cache, monkeypatch):
    monkeypatch.setattr(cache_warmup, '_load', lambda *args: {'standard_words': []})
    def clean():
        assert all(cache.client.exists(cache.key(k, p)) for k, p in DEFAULTS)
        return False
    monkeypatch.setattr(cache, 'cleanup', clean)
    assert asyncio.run(cache_warmup.warm_once(cache, None, pause=0))


def test_cleanup_scans_pages_eventually_removes_stale_and_shares_cooldown(cache, monkeypatch):
    populate(cache)
    keys = [f'{cache.root}:default:search-v2:old:old:entries:{i}' for i in range(300)]
    with cache.client.pipeline() as pipe:
        for key in keys:
            pipe.set(key, 'old')
        pipe.execute()
    scan = cache.client.scan
    scans = []
    def measured(*args, **kwargs):
        scans.append((args, kwargs))
        return scan(*args, **kwargs)
    monkeypatch.setattr(cache.client, 'scan', measured)
    monkeypatch.setattr(cache.client, 'scan_iter', lambda *args, **kwargs: pytest.fail('full traversal'))
    pending = cache.cleanup()
    assert pending is True
    assert 1 <= len(scans) <= 2
    assert any(cache.client.exists(key) for key in keys)
    for _ in range(100):
        if not pending:
            break
        cache.client.delete(cache.root + ':cleanup-gate')
        before = len(scans)
        pending = cache.cleanup()
        assert len(scans)-before <= 2
    assert pending is False
    assert not any(cache.client.exists(key) for key in keys)
    assert all(cache.client.exists(cache.key(k, p)) for k, p in DEFAULTS)
    other = VocabularyCache(cache.client, cache.db_path, namespace=cache.root.split(':')[0])
    before = len(scans)
    assert other.cleanup() is False
    assert len(scans) == before


def test_failed_cleanup_does_not_advance_shared_cursor(cache, monkeypatch):
    cache.state()
    progress = cache.root + ':cleanup-progress'
    cache.client.hset(progress, mapping={'default': '0', 'ondemand': '0', 'pending': '1'})
    scan = cache.client.scan
    def fail(*args, **kwargs):
        raise RuntimeError('test scan failure')
    monkeypatch.setattr(cache.client, 'scan', fail)
    with pytest.raises(RuntimeError, match='test scan failure'):
        cache.cleanup()
    assert cache.client.hget(progress, 'default') == '0'
    assert cache.client.hget(progress, 'ondemand') == '0'


def test_background_busy_does_not_enter_online_waiter_queue(monkeypatch, tmp_path):
    monkeypatch.setenv('TOPONYMS_LOCK_DIR', str(tmp_path/'locks'))
    entered, release = threading.Event(), threading.Event()
    def operation():
        entered.set()
        assert release.wait(3)
    original_slot = resources._slot
    categories = []
    @contextmanager
    def recorded(path, category, count):
        categories.append(category)
        with original_slot(path, category, count):
            yield
    monkeypatch.setattr(resources, '_slot', recorded)
    async def scenario():
        first = asyncio.create_task(resources.run_bounded('test', operation, expensive=True))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            categories.clear()
            with pytest.raises(resources.BackgroundBusy):
                await resources.run_bounded('test', lambda: pytest.fail('must defer'), expensive=True, background=True)
            assert 'vocabulary-waiters' not in categories
        finally:
            release.set()
            await first
    asyncio.run(scenario())


def test_background_cache_miss_does_not_wait_for_online_compute(cache):
    from app.service.vocabulary.resources import BackgroundBusy
    key = cache.key('entries', {})
    import hashlib
    lock_key = cache.root + ':compute:' + hashlib.md5(key.encode()).hexdigest()
    cache.client.set(lock_key, 'online', ex=30)
    async def loader():
        pytest.fail('must not duplicate online computation')
    async def scenario():
        with pytest.raises(BackgroundBusy):
            await cache.acall('entries', {}, loader, wait_for_lease=False)
        assert cache.client.get(lock_key) == 'online'
    asyncio.run(scenario())


def test_background_warmup_defers_and_releases_owned_leases(cache, monkeypatch):
    populate(cache)
    cache.client.delete(cache.key('map-points', {}))
    async def busy(*args, **kwargs):
        assert kwargs['background'] is True
        raise resources.BackgroundBusy()
    monkeypatch.setattr(resources, 'run_bounded', busy)
    assert asyncio.run(cache_warmup.warm_once(cache, None, pause=0, background=True)) is False
    assert not cache.client.exists(cache.root+':warm-lock')
    assert cache.read(cache.key('map-points', {})) is None


def test_cleanup_lost_gate_cannot_commit_cursor(cache, monkeypatch):
    cache.state()
    progress = cache.root+':cleanup-progress'
    cache.client.hset(progress, mapping={'default': '0', 'ondemand': '0', 'pending': '1'})
    scan = cache.client.scan
    def replaced(*args, **kwargs):
        result = scan(*args, **kwargs)
        cache.client.set(cache.root+':cleanup-gate', 'new-owner', ex=60)
        return result
    monkeypatch.setattr(cache.client, 'scan', replaced)
    assert cache.cleanup() is True
    assert cache.client.hget(progress, 'default') == '0'
    assert cache.client.hget(progress, 'ondemand') == '0'
    assert cache.client.get(cache.root+':cleanup-gate') == 'new-owner'


def test_cleanup_failure_releases_gate_for_retry(cache, monkeypatch):
    cache.state()
    monkeypatch.setattr(cache.client, 'scan', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('scan failed')))
    with pytest.raises(RuntimeError, match='scan failed'):
        cache.cleanup()
    assert not cache.client.exists(cache.root+':cleanup-gate')


def test_background_deferral_still_advances_cleanup(cache, monkeypatch):
    populate(cache)
    cache.client.delete(cache.key('map-points', {}))
    cleanups = []
    monkeypatch.setattr(cache, 'cleanup', lambda: cleanups.append(True))
    async def busy(*args, **kwargs):
        raise resources.BackgroundBusy()
    monkeypatch.setattr(resources, 'run_bounded', busy)
    assert asyncio.run(cache_warmup.warm_once(cache, None, pause=0, background=True)) is False
    assert cleanups == [True]


def test_version_change_during_pause_stops_next_query(cache, monkeypatch, pause_calls):
    calls = []
    monkeypatch.setattr(cache_warmup, '_load', lambda factory, kind, params: calls.append(kind) or {'standard_words': []})
    original_sleep = asyncio.sleep
    async def change(seconds):
        if seconds == .12345:
            cache.invalidate('entries')
        await original_sleep(seconds)
    monkeypatch.setattr(asyncio, 'sleep', change)
    assert asyncio.run(cache_warmup.warm_once(cache, None, pause=.12345)) is False
    assert calls == ['sql-count']
    assert not cache.client.exists(cache.root+':warm-lock')


def test_background_releases_expensive_slot_if_heavy_is_busy(monkeypatch, tmp_path):
    from contextlib import ExitStack
    monkeypatch.setenv('TOPONYMS_LOCK_DIR', str(tmp_path/'locks'))
    with ExitStack() as held:
        for _ in range(2):
            held.enter_context(resources._slot(resources.TOPONYMS_DB_PATH, 'heavy', 2))
        async def scenario():
            with pytest.raises(resources.BackgroundBusy):
                await resources.run_bounded('test', lambda: pytest.fail('busy'), background=True, expensive=True)
        asyncio.run(scenario())
        with resources._slot(resources.TOPONYMS_DB_PATH, 'vocabulary-expensive', 1):
            pass
