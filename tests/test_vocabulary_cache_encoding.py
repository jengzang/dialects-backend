"""Cache admission must not copy or encode a complete oversized response."""
import asyncio
from dataclasses import dataclass
import json

import pytest

from app.service.vocabulary import cache as module
from tests.test_vocabulary_cache import cache
from tests.test_vocabulary_query_resources import database


@dataclass
class Words:
    standard_words: list
    total: int


@pytest.mark.parametrize('value', [
    Words([{'word': '廣東', 'variants': ['广东', '廣東']}], 1),
    {'text': '"\\\n\t\r\b\f\u0000中文😀', 'values': [None, True, False, 1, -2, 1.25]},
    {'tuple': ('a', 2), '_sa_hidden': 'excluded'},
])
def test_bounded_encoding_preserves_json_value_and_exact_utf8_boundary(value):
    expected = module.encoded(value)
    size = len(expected.encode('utf-8'))
    result = module.bounded_encoded(value, size)
    assert json.loads(result) == json.loads(expected)
    assert len(result.encode('utf-8')) == size
    assert module.bounded_encoded(value, size - 1) is None


def test_oversized_dataclass_does_not_deepcopy_or_visit_tail():
    class Unvisited:
        def __deepcopy__(self, memo):
            pytest.fail('dataclass was copied before checking the size')
    assert module.bounded_encoded(Words(['中' * 10000, Unvisited()], 2), 128) is None


def test_long_string_is_escaped_in_bounded_chunks(monkeypatch):
    dumps = json.dumps
    def checked(value, **kwargs):
        if isinstance(value, str):
            assert len(value) <= 1024
        return dumps(value, **kwargs)
    monkeypatch.setattr(module.json, 'dumps', checked)
    assert module.bounded_encoded({'field': '😀' * 1000000}, 128) is None


def test_unsupported_values_skip_optional_cache():
    assert module.bounded_encoded({'value': object()}, 128) is None


@pytest.mark.parametrize('asynchronous', [False, True])
def test_oversized_result_is_returned_whole_without_redis_payload(cache, monkeypatch, asynchronous):
    value = Words([{'word': '中文' * 1000}] * 2000, 2000)
    original = cache.client.eval
    def checked(script, *args):
        assert script != module._WRITE, 'oversized payload was sent to Redis'
        return original(script, *args)
    monkeypatch.setattr(cache.client, 'eval', checked)
    encoder = module.jsonable_encoder
    def checked_encoder(item):
        assert item is not value, 'complete result converted before size check'
        return encoder(item)
    monkeypatch.setattr(module, 'jsonable_encoder', checked_encoder)
    if asynchronous:
        async def load():
            return value
        result = asyncio.run(cache.acall('standard-words', {'limit': None}, load))
    else:
        result = cache.call('standard-words', {'limit': None}, lambda: value)
    assert result is value
    assert len(result.standard_words) == 2000
    assert not cache.client.exists(cache.key('standard-words', {'limit': None}))


def test_permanent_default_still_caches_above_demand_budget(cache):
    value = Words([{'word': '中文' * 1000}], 999)
    cache.store('standard-words', {'limit': 1000}, value, cache.state())
    assert cache.read(cache.key('standard-words', {'limit': 1000})) == json.loads(module.encoded(value))


def test_small_demand_payload_keeps_revision_guard(cache):
    value = {'items': ['中文'], 'total': 1}
    state = cache.state()
    cache.invalidate('entries')
    cache.store('entries', {'q': '中文'}, value, state)
    assert cache.read(cache.key('entries', {'q': '中文'})) is None


@pytest.mark.parametrize('kind,params', [
    ('items', {}), ('standard_words', {'limit': None}),
    ('map_points', {}), ('map_items', {'standard_words': ['太阳']}),
])
def test_real_query_result_shapes_preserve_every_field(database, kind, params):
    from app.service.vocabulary import query
    _, session, _ = database
    value = getattr(query, 'query_vocabulary_' + kind)(session=session, **params)
    assert json.loads(module.bounded_encoded(value, 128 * 1024)) == json.loads(module.encoded(value))
