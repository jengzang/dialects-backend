"""Home-page shortcuts use permanent, actively refreshed Redis results."""
import asyncio

import pytest

from app.service.vocabulary.cache import DEFAULTS, normalize
from app.service.vocabulary.cache_warmup import warm_once
from app.service.vocabulary.database import create_vocabulary_engine_and_session
from app.service.vocabulary.models import Base, VocabularyEntry, VocabularyLocation
from tests.test_vocabulary_cache import cache
from tests.test_vocabulary_cache_routes import api


SPIDER = ('entries', {'q': '蜘蛛', 'search_fields': ['definition', 'headword'], 'page': 1, 'page_size': 50})
EARTHWORM = ('map-items', {'standard_words': ['蚯蚓']})


@pytest.mark.parametrize('path,params,query_name', [
    ('entries', SPIDER[1], 'query_vocabulary_items'),
    ('map-items', EARTHWORM[1], 'query_vocabulary_map_items'),
])
def test_real_shortcut_http_requests_hit_prewarmed_keys(api, cache, monkeypatch, path, params, query_name):
    from app.routes import vocabulary
    client, _ = api
    monkeypatch.setattr(vocabulary, query_name, lambda **kwargs: pytest.fail('prewarmed HTTP request queried SQLite'))
    assert client.get('/vocabulary/search/' + path, params=params).status_code == 200
    assert cache.client.ttl(cache.key(path, params)) == -1


@pytest.fixture
def factory(cache):
    engine, factory = create_vocabulary_engine_and_session(cache.db_path)
    Base.metadata.create_all(engine)
    with factory() as session:
        session.add(VocabularyLocation(user_id=1, location_name='甲', coordinates='106,27'))
        for word in ('蜘蛛', '蚯蚓'):
            session.add(VocabularyEntry(user_id=1, location_name='甲', standard_word=word,
                                        local_expression=word, ipa='a'))
        session.commit()
    yield factory
    engine.dispose()


def test_shortcuts_prewarm_without_http_and_survive_demand_eviction(cache, factory):
    assert asyncio.run(warm_once(cache, factory, pause=0))
    for kind, params in (SPIDER, EARTHWORM):
        assert any(k == kind and normalize(k, p) == normalize(kind, params) for k, p in DEFAULTS)
        assert cache.client.ttl(cache.key(kind, params)) == -1
    spider = cache.read(cache.key(*SPIDER))
    worm = cache.read(cache.key(*EARTHWORM))
    assert spider['items'][0]['standard_word'] == '蜘蛛'
    assert worm['points'][0]['items'][0]['standard_word'] == '蚯蚓'
    for q in ('a', 'b', 'c'):
        cache.call('entries', {'q': q}, lambda: {})
    assert cache.read(cache.key(*SPIDER)) == spider
    assert cache.read(cache.key(*EARTHWORM)) == worm
    assert cache.client.ttl(cache.key(*SPIDER)) == -1
    assert cache.client.ttl(cache.key(*EARTHWORM)) == -1
    # Other search fields, pages and words remain ordinary demand entries.
    assert not cache.describe('entries', {**SPIDER[1], 'page': 2})[1]
    assert not cache.describe('entries', {**SPIDER[1], 'search_fields': ['definition']})[1]
    assert not cache.describe('map-items', {'standard_words': ['蜘蛛']})[1]


def test_shortcuts_refresh_after_entries_and_location_changes(cache, factory):
    assert asyncio.run(warm_once(cache, factory, pause=0))
    old_keys = [cache.key(*preset) for preset in (SPIDER, EARTHWORM)]
    with factory() as session:
        for row in session.query(VocabularyEntry):
            row.local_expression = '新' + row.standard_word
        session.commit()
    cache.invalidate('entries')
    assert asyncio.run(warm_once(cache, factory, pause=0))
    assert cache.read(cache.key(*SPIDER))['items'][0]['local_expression'] == '新蜘蛛'
    assert cache.read(cache.key(*EARTHWORM))['points'][0]['items'][0]['local_expression'] == '新蚯蚓'
    assert all(cache.key(*preset) != key for preset, key in zip((SPIDER, EARTHWORM), old_keys))
    old_worm = cache.key(*EARTHWORM)
    with factory() as session:
        session.query(VocabularyLocation).update({'coordinates': '107,28'})
        session.commit()
    cache.invalidate('locations')
    assert asyncio.run(warm_once(cache, factory, pause=0))
    assert cache.key(*EARTHWORM) != old_worm
    assert cache.read(cache.key(*EARTHWORM))['points'][0]['longitude'] == 107
    assert cache.client.ttl(cache.key(*EARTHWORM)) == -1
