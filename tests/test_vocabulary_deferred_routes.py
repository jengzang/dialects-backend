"""HTTP, real Redis and background-lifecycle coverage for optional totals."""
import asyncio
import json

import pytest

from tests.test_vocabulary_cache_routes import api, cache


def test_opt_in_returns_pending_then_same_count_is_reused_by_legacy(cache, api):
    client, _ = api
    params = dict(q='太阳', page_size=1, defer_total=True)
    # Add a second match without generating a new request/cache revision.
    from app.service.vocabulary.models import VocabularyEntry
    with api[1]() as session:
        session.add(VocabularyEntry(user_id=1, location_name='甲', standard_word='太阳', local_expression='日头', ipa='b'))
        session.commit()
    first = client.get('/vocabulary/search/entries', params=params)
    assert first.status_code == 200, first.text
    assert first.json()['total'] is None and first.json()['has_more'] is True
    assert len(first.json()['items']) == 1
    second = client.get('/vocabulary/search/entries', params=params)
    assert second.json()['total'] == 2 and second.json()['has_more'] is True
    last = client.get('/vocabulary/search/entries', params={**params, 'page': 2})
    assert last.json()['total'] == 2 and last.json()['has_more'] is False
    # Exactly one existing scalar cache key, with no deferred/page variant.
    scalar_keys = list(cache.client.scan_iter(match=cache.root + ':*:entries-count:*'))
    assert len(scalar_keys) == 1
    assert client.get('/vocabulary/search/entries', params={'q': '太阳', 'page_size': 1}).json()['total'] == 2


def test_short_page_infers_total_without_scheduling_count(cache, api, monkeypatch):
    from app.service.vocabulary import deferred_count
    async def unexpected(*args, **kwargs):
        pytest.fail('short result scheduled a count')
    monkeypatch.setattr(deferred_count, 'complete_count', unexpected)
    response = api[0].get('/vocabulary/search/entries', params={'q': '太阳', 'defer_total': True})
    assert response.json()['total'] == 1 and response.json()['has_more'] is False
    assert len(list(cache.client.scan_iter(match=cache.root + ':*:entries-count:*'))) == 1


def test_deferred_mode_reuses_prewarmed_legacy_complete_response(cache, api, monkeypatch):
    from app.service.vocabulary import deferred_count
    def unexpected(**kwargs): pytest.fail('known complete response queried SQLite')
    monkeypatch.setattr(deferred_count, 'query_vocabulary_items', unexpected)
    response = api[0].get('/vocabulary/search/entries', params={'defer_total': True})
    assert response.status_code == 200
    assert response.json()['total'] == 1 and response.json()['has_more'] is False


def test_response_body_is_sent_before_background_count(cache, api, monkeypatch):
    from app.service.vocabulary import deferred_count
    from app.service.vocabulary.models import VocabularyEntry
    with api[1]() as session:
        session.add(VocabularyEntry(user_id=1, location_name='甲', standard_word='太阳', local_expression='日头', ipa='b'))
        session.commit()
    cache.invalidate('entries')
    sent = []
    counted = []
    original = deferred_count.query_vocabulary_items
    def observe(**kwargs):
        if kwargs.get('_count_only'):
            assert any(m['type'] == 'http.response.body' for m in sent)
            counted.append(True)
        return original(**kwargs)
    monkeypatch.setattr(deferred_count, 'query_vocabulary_items', observe)
    async def scenario():
        async def send(message): sent.append(message)
        async def receive(): return {'type': 'http.request', 'body': b'', 'more_body': False}
        await api[0].app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
            'method': 'GET', 'scheme': 'http', 'path': '/vocabulary/search/entries',
            'raw_path': b'/vocabulary/search/entries', 'query_string': b'page_size=1&defer_total=true',
            'headers': [], 'client': ('test', 1), 'server': ('test', 80), 'root_path': ''}, receive, send)
    asyncio.run(scenario())
    payload = json.loads(next(m['body'] for m in sent if m['type'] == 'http.response.body'))
    assert payload['total'] is None and payload['has_more'] is True
    assert counted == [True]
    assert len(list(cache.client.scan_iter(match=cache.root + ':*:entries-count:*'))) == 1


@pytest.mark.parametrize('reason', ['global_busy', 'cooldown', 'version', 'slot_busy', 'redis'])
def test_background_skip_is_nonblocking_and_does_no_sql(cache, api, monkeypatch, reason):
    from app.service.vocabulary import deferred_count
    from app.service.vocabulary.resources import BackgroundBusy
    from redis.exceptions import ConnectionError
    state = cache.state()
    if reason == 'global_busy': cache.client.set(cache.root + ':count-active', 'other', ex=120)
    if reason == 'cooldown': cache.client.set(cache.root + ':count-cooldown', '1', ex=15)
    if reason == 'version': cache.invalidate('entries')
    if reason == 'slot_busy':
        async def busy(*args, **kwargs): raise BackgroundBusy()
        monkeypatch.setattr(deferred_count, 'run_bounded', busy)
    if reason == 'redis':
        monkeypatch.setattr(cache, 'state', lambda: (_ for _ in ()).throw(ConnectionError('unavailable')))
    monkeypatch.setattr(deferred_count, 'query_vocabulary_items', lambda **kwargs: pytest.fail('skip executed query'))
    asyncio.run(deferred_count.complete_count(cache, api[1], {}, state))
    if reason != 'global_busy': assert not cache.client.exists(cache.root + ':count-active')


def test_failure_cools_down_and_cleans_up(cache, api, monkeypatch):
    from app.service.vocabulary import deferred_count
    monkeypatch.setattr(deferred_count, 'query_vocabulary_items', lambda **kwargs: (_ for _ in ()).throw(RuntimeError('broken')))
    asyncio.run(deferred_count.complete_count(cache, api[1], {}, cache.state()))
    assert 0 < cache.client.ttl(cache.root + ':count-cooldown') <= 15
    assert not cache.client.exists(cache.root + ':count-active')


def test_invalidation_during_count_cannot_publish_new_revision(cache, api, monkeypatch):
    from app.service.vocabulary import deferred_count
    original = deferred_count.query_vocabulary_items
    def change(**kwargs):
        result = original(**kwargs)
        cache.invalidate('entries')
        return result
    monkeypatch.setattr(deferred_count, 'query_vocabulary_items', change)
    # Invalidating before original store is tested via the actual execute callback.
    original_store = cache.store
    def store(kind, params, value, state):
        cache.invalidate('entries')
        return original_store(kind, params, value, state)
    monkeypatch.setattr(cache, 'store', store)
    asyncio.run(deferred_count.complete_count(cache, api[1], {'q': '太阳'}, cache.state()))
    assert not list(cache.client.scan_iter(match=cache.root + ':*:entries-count:*'))


def test_pending_result_is_not_cached(cache):
    state = cache.state()
    params = {'q': '太阳', 'defer_total': True}
    cache.store('entries', params, {'items': [], 'total': None, 'has_more': True}, state)
    assert cache.read(cache.describe('entries', params, state)[0]) is None


def test_cache_outage_still_returns_lookahead_without_background(api, monkeypatch):
    from app.service.vocabulary import cache as module
    monkeypatch.setattr(module, 'get_vocabulary_cache', lambda path: None)
    response = api[0].get('/vocabulary/search/entries', params={'defer_total': True, 'q': '太阳'})
    assert response.status_code == 200
    assert response.json()['total'] == 1 and response.json()['has_more'] is False


def test_sqlite_deadline_interrupts_and_restores_pooled_connection(cache, api, monkeypatch):
    from app.service.vocabulary import deferred_count
    with api[1]() as session:
        conn = session.connection().connection
        conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
                         ((1, '甲', '太阳', '日头', 'a') for _ in range(5000)))
        session.commit()
    monkeypatch.setattr(deferred_count, 'COUNT_SECONDS', -1)
    asyncio.run(deferred_count.complete_count(cache, api[1], {'q': '不存在'}, cache.state()))
    assert cache.client.exists(cache.root + ':count-cooldown')
    assert not list(cache.client.scan_iter(match=cache.root + ':*:entries-count:*'))
    with api[1]() as session:
        conn = session.connection().connection
        assert conn.execute('PRAGMA busy_timeout').fetchone()[0] == 10000
        assert conn.execute('SELECT COUNT(*) FROM vocabulary_entries WHERE standard_word LIKE ?', ('%太阳%',)).fetchone()[0] == 5001


def test_existing_legacy_computation_lock_skips_count(cache, api, monkeypatch):
    import hashlib
    from app.service.vocabulary import deferred_count
    from app.service.vocabulary.query import query_vocabulary_items
    params = {'q': '太阳'}
    signature = {}
    with api[1]() as session:
        def capture(sql, values, compute):
            signature.update(sql=sql, values=values)
            return None
        query_vocabulary_items(session=session, defer_total=True, _count_resolver=capture, **params)
    key = cache.key('entries-count', signature)
    lock = cache.root + ':compute:' + hashlib.md5(key.encode()).hexdigest()
    cache.client.set(lock, 'legacy-owner', ex=120)
    original = deferred_count.query_vocabulary_items
    def prohibit_count(**kwargs):
        resolve = kwargs['_count_resolver']
        kwargs['_count_resolver'] = lambda sql, values, execute: resolve(sql, values, lambda: pytest.fail('duplicated count'))
        return original(**kwargs)
    monkeypatch.setattr(deferred_count, 'query_vocabulary_items', prohibit_count)
    asyncio.run(deferred_count.complete_count(cache, api[1], params, cache.state()))
    assert cache.client.get(lock) == 'legacy-owner'
    assert not cache.client.exists(cache.root + ':count-active')


def test_page_cache_pending_is_not_kept_and_count_cache_survives_page_changes(cache, api):
    client, factory = api
    from app.service.vocabulary.models import VocabularyEntry
    with factory() as session:
        session.add(VocabularyEntry(user_id=1, location_name='甲', standard_word='太阳', local_expression='日头', ipa='b'))
        session.commit()
    cache.client.set(cache.root + ':count-active', 'occupied', ex=120)
    first = client.get('/vocabulary/search/entries', params={'q': '太阳', 'page_size': 1, 'defer_total': True}).json()
    second = client.get('/vocabulary/search/entries', params={'q': '太阳', 'page_size': 1, 'defer_total': True}).json()
    assert first['total'] is None and second['total'] is None
    assert cache.read(cache.key('entries', {'q': '太阳', 'page_size': 1, 'defer_total': True})) is None
    cache.client.delete(cache.root + ':count-active')
    # A skipped job is retried by a later real request, without a queued task.
    assert client.get('/vocabulary/search/entries', params={'q': '太阳', 'page_size': 1, 'defer_total': True}).json()['total'] is None
    assert client.get('/vocabulary/search/entries', params={'q': '太阳', 'page_size': 2, 'defer_total': True}).json()['total'] == 2


def test_cancel_during_global_claim_does_not_leave_a_lease(cache, api, monkeypatch):
    import threading
    from app.service.vocabulary import deferred_count
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = cache.client.set
    def delayed(key, *args, **kwargs):
        if key == cache.root + ':count-active':
            entered.set()
            assert release.wait(5)
            try:
                return original(key, *args, **kwargs)
            finally:
                finished.set()
        return original(key, *args, **kwargs)
    monkeypatch.setattr(cache.client, 'set', delayed)
    async def scenario():
        task = asyncio.create_task(deferred_count.complete_count(cache, api[1], {}, cache.state()))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            task.cancel()
            await asyncio.sleep(.01)
            release.set()
            assert await asyncio.to_thread(finished.wait, 5)
            with pytest.raises(asyncio.CancelledError):
                await task
            assert not cache.client.exists(cache.root + ':count-active')
        finally:
            release.set()
    asyncio.run(scenario())


@pytest.mark.parametrize('cancel', [False, True])
def test_running_count_is_single_and_drained_before_lease_release(cache, api, monkeypatch, cancel):
    import threading
    from app.service.vocabulary import deferred_count
    entered, release = threading.Event(), threading.Event()
    original = deferred_count.query_vocabulary_items
    calls = []
    def delayed(**kwargs):
        calls.append(kwargs['session'])
        entered.set()
        assert release.wait(5)
        return original(**kwargs)
    monkeypatch.setattr(deferred_count, 'query_vocabulary_items', delayed)
    async def scenario():
        state = cache.state()
        task = asyncio.create_task(deferred_count.complete_count(cache, api[1], {'q': '太阳'}, state))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            # A different condition must also skip while this count owns the slot.
            await deferred_count.complete_count(cache, api[1], {'q': '月亮'}, state)
            assert len(calls) == 1
            if cancel:
                task.cancel()
                await asyncio.sleep(.01)
                assert not task.done()
                assert cache.client.exists(cache.root + ':count-active')
            release.set()
            if cancel:
                with pytest.raises(asyncio.CancelledError): await task
            else:
                await task
            assert not cache.client.exists(cache.root + ':count-active')
            assert not list(cache.client.scan_iter(match=cache.root + ':compute:*'))
        finally:
            release.set()
    asyncio.run(scenario())


def test_redis_failure_on_foreground_still_returns_data(api, cache, monkeypatch):
    from redis.exceptions import ConnectionError
    def unavailable(): raise ConnectionError('unavailable')
    monkeypatch.setattr(cache, 'state', unavailable)
    response = api[0].get('/vocabulary/search/entries', params={'q': '太阳', 'defer_total': True})
    assert response.status_code == 200
    assert response.json()['total'] == 1 and response.json()['has_more'] is False
