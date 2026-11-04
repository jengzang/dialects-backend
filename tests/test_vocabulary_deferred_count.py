"""Lookahead returns correct pages without requiring an exact count."""
import pytest

from app.service.vocabulary.query import query_vocabulary_items
from tests.test_vocabulary_query_resources import database


@pytest.mark.parametrize('params', [
    {}, {'q': '太阳'}, {'q': '日', 'search_fields': ['headword']},
    {'q': '备', 'search_fields': ['detail']}, {'q': 'a', 'search_fields': ['pronunciation']},
    {'q': '广东', 'search_fields': ['location']}, {'locations': ['贵州']},
    {'province': '广东'}, {'regions': ['官话/西南']}, {'standard_words': ['太阳']},
    {'q': '%'}, {'q': '不存在'},
])
@pytest.mark.parametrize('page', [1, 2, 4, 5])
def test_deferred_pages_match_exact_without_result_count(database, params, page):
    _, session, sql = database
    expected = query_vocabulary_items(session=session, **params, page=page, page_size=1)
    sql.clear()
    actual = query_vocabulary_items(session=session, **params, page=page, page_size=1, defer_total=True)
    assert actual.items == expected.items
    assert actual.has_more == (page < expected.total)
    if not actual.has_more and (page == 1 or actual.items):
        assert actual.total == expected.total
    else:
        assert actual.total is None
    assert not any(s.startswith('SELECT COUNT(*)') or 'vocabulary_scope_count' in s for s in sql)


@pytest.mark.parametrize('size', [4, 5, 200])
def test_exactly_one_page_needs_no_background_count(database, size):
    _, session, _ = database
    result = query_vocabulary_items(session=session, defer_total=True, page_size=size)
    assert result.total == 4 and result.has_more is False and len(result.items) == 4


@pytest.mark.parametrize('total,page', [(0, 1), (4, 1), (4, 5)])
def test_cached_total_shortcuts_and_has_more(database, total, page):
    _, session, sql = database
    result = query_vocabulary_items(session=session, defer_total=True, page=page, page_size=1,
        _count_resolver=lambda sql, values, compute: total)
    assert result.total == total
    assert result.has_more == (page < total)
    if page > total:
        assert result.items == []
        assert not any(s.startswith(('SELECT', 'WITH')) for s in sql)


def test_count_only_reuses_plan_without_reading_page(database):
    _, session, sql = database
    result = query_vocabulary_items(session=session, q='日', search_fields=['headword'],
        locations=['贵州'], _count_only=True)
    assert result.total == 2 and result.items == []
    assert any('vocabulary_scope_count' in s for s in sql)
    assert not any('ORDER BY e.id DESC' in s for s in sql)


def test_count_cache_signature_does_not_depend_on_deferred_mode(database):
    conn, session, _ = database
    keys = []
    def resolve(sql, values, compute):
        keys.append((sql, values))
        return None
    query_vocabulary_items(session=session, q='太阳', defer_total=True, _count_resolver=resolve)
    query_vocabulary_items(session=session, q='太阳',
        _count_loader=lambda sql, values: (keys.append((sql, values)) or conn.execute(sql, values).fetchone()[0]))
    assert keys[0] == keys[1]
