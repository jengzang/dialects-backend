"""Prewarming cannot hold the online cache computation lease or worker readiness."""
import asyncio
from types import SimpleNamespace
import threading

import pytest

from app.service.vocabulary import cache as cache_module, cache_warmup, resources
from app.service.vocabulary.cache import DEFAULTS
from tests.test_vocabulary_cache import cache


@pytest.mark.parametrize('kind,params', [('entries', {}), ('map-items', {'standard_words': ['蚯蚓']})])
def test_online_query_loads_without_waiting_for_running_prewarm(cache, monkeypatch, tmp_path, kind, params):
    monkeypatch.setenv('TOPONYMS_LOCK_DIR', str(tmp_path / 'locks'))
    monkeypatch.setattr(cache_module, 'get_vocabulary_cache', lambda path: cache)
    state = cache.state()
    for k, p in DEFAULTS:
        cache.store(k, p, {'cached': True}, state)
    cache.client.delete(cache.key(kind, params))
    entered, release = threading.Event(), threading.Event()
    calls = []
    def warm_load(*args):
        calls.append('warm')
        entered.set()
        assert release.wait(5)
        return {'source': 'warm'}
    monkeypatch.setattr(cache_warmup, '_load', warm_load)
    db = SimpleNamespace(get_bind=lambda: SimpleNamespace(url=SimpleNamespace(database=cache.db_path)))
    def online(**kwargs):
        calls.append('online')
        return {'source': 'online'}
    async def scenario():
        task = asyncio.create_task(cache_warmup.warm_once(cache, None, pause=0, background=True))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            # A second worker must not start another prewarm for this database.
            assert await cache_warmup.warm_once(cache, None, pause=0, background=True) is False
            assert await asyncio.wait_for(cache_module.cached_search(kind, db, online, **params), 1) == {'source': 'online'}
            assert not task.done()
            assert calls == ['warm', 'online']
            release.set()
            assert await task
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())


@pytest.mark.parametrize('kind,params', [
    ('entries', {}), ('map-items', {'standard_words': ['蚯蚓']}),
    ('map-points', {}), ('location-options', {}), ('standard-words', {'limit': 1000}),
])
def test_only_standard_words_uses_expensive_slot_online_and_in_prewarm(cache, monkeypatch, kind, params):
    monkeypatch.setattr(cache_module, 'get_vocabulary_cache', lambda path: None)
    observed = []
    async def run(path, operation, *args, **kwargs):
        observed.append(kwargs['expensive'])
        return operation(*args)
    monkeypatch.setattr(resources, 'run_bounded', run)
    db = SimpleNamespace(get_bind=lambda: SimpleNamespace(url=SimpleNamespace(database=cache.db_path)))
    asyncio.run(cache_module.cached_search(kind, db, lambda **kwargs: {}, **params))
    assert observed == [kind == 'standard-words']
    state = cache.state()
    for k, p in DEFAULTS:
        cache.store(k, p, {}, state)
    cache.client.delete(cache.key(kind, params))
    observed.clear()
    monkeypatch.setattr(cache_warmup, '_load', lambda *args: {})
    assert asyncio.run(cache_warmup.warm_once(cache, None, pause=0, background=True))
    assert observed == [kind == 'standard-words']
