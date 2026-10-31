"""Scoped non-covering standard-word search and covering/fallback boundaries."""
from dataclasses import asdict

import pytest

from app.service.vocabulary import query
from tests.test_vocabulary_query_resources import database


@pytest.mark.parametrize('fields', [['headword'], ['definition', 'headword']])
@pytest.mark.parametrize('locations', [['贵州'], ['贵州', '广东'], ['不存在地点']])
def test_scoped_noncovering_search_uses_identity_traversal(database, fields, locations):
    _, session, statements = database
    query.query_vocabulary_standard_words(session=session, q='日头',
        search_fields=fields, locations=locations, limit=None)
    sql = next(s for s in statements if s.startswith('SELECT'))
    assert 'INDEXED BY idx_vocabulary_entries_user_location' in sql


@pytest.mark.parametrize('options', [
    {'search_fields': ['definition']}, {'search_fields': ['detail']},
    {'search_fields': ['pronunciation']}, {'search_fields': ['headword', 'location']},
    {'q': '%'}, {'q': '日_'}, {'q': '日\0头'}, {'locations': ['贵_']},
    {'q': '贵州'}, {'locations': ['%']}, {'province': '贵州'},
])
def test_other_scoped_shapes_keep_automatic_plan(database, options):
    _, session, statements = database
    params = dict(q='日头', search_fields=['headword'], locations=['贵州'])
    params.update(options)
    query.query_vocabulary_standard_words(session=session, limit=None, **params)
    assert 'INDEXED BY' not in next(s for s in statements if s.startswith('SELECT'))


@pytest.mark.parametrize('fields', [['headword'], ['definition', 'headword']])
@pytest.mark.parametrize('q', ['日头', '共同', '不存在', 'a', '太陽'])
def test_all_groups_equal_automatic_plan(database, monkeypatch, fields, q):
    conn, session, _ = database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES (?,?,?,?,?)',
        [(i % 3 + 1, '同名' if i % 2 else '孤立地点', '太阳' if i % 2 else '太陽',
          '共同日头' if i % 5 else '太陽a', 'a') for i in range(303)])
    conn.commit()
    params = dict(session=session, q=q, search_fields=fields,
                  locations=['贵州', '孤立'], limit=None)
    actual = query.query_vocabulary_standard_words(**params)
    assert actual.total == len(actual.standard_words)
    monkeypatch.setattr(query, '_prefer_location_identity_scan', lambda **kwargs: False)
    expected = query.query_vocabulary_standard_words(**params)
    assert asdict(actual) == asdict(expected)


def test_scoped_standard_query_normalizes_iterables_once(database):
    _, session, statements = database
    result = query.query_vocabulary_standard_words(session=session, q='日头',
        search_fields=iter(['headword']), locations=iter(['贵州']), limit=None)
    assert result.total == 1
    assert result.standard_words[0].entry_count == 2
    assert 'INDEXED BY idx_vocabulary_entries_user_location' in next(s for s in statements if s.startswith('SELECT'))
