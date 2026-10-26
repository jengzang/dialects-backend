"""Location-scoped default fuzzy queries: plans and complete result regression."""
from dataclasses import asdict

import pytest

from app.service.vocabulary import query
from tests.test_vocabulary_query_resources import database


@pytest.mark.parametrize('params', [
    {'q': '日头', 'locations': ['贵州']},
    {'q': '日头', 'search_fields': ['all'], 'locations': ['贵州']},
    {'q': '日头', 'search_fields': ['detail', 'definition', 'pronunciation', 'headword'], 'locations': ['贵州']},
    {'q': '无匹配关键词', 'locations': ['不存在地点']},
])
def test_default_fuzzy_location_count_uses_identity_before_content(database, params):
    _, session, statements = database
    query.query_vocabulary_items(session=session, **params)
    count = next(s for s in statements if s.startswith('SELECT COUNT(*)'))
    assert 'INDEXED BY idx_vocabulary_entries_user_location' in count
    assert count.index("COALESCE(e.location_name, '') LIKE") < count.index("COALESCE(e.standard_word, '') LIKE")
    assert 'LEFT JOIN' not in count
    pages = [s for s in statements if s.startswith('SELECT') and not s.startswith('SELECT COUNT(*)')]
    assert all('INDEXED BY' not in s for s in pages)


@pytest.mark.parametrize('params', [
    {}, {'locations': ['贵州']}, {'q': '日头'},
    {'q': '日头', 'locations': ['贵州'], 'search_fields': ['definition']},
    {'q': '备注', 'locations': ['贵州'], 'search_fields': ['detail']},
    {'q': '日头', 'locations': ['贵州'], 'search_fields': ['headword']},
    {'q': '日头', 'locations': ['贵州'], 'search_fields': ['headword', 'location']},
    {'q': '日头', 'locations': ['贵州'], 'province': '贵州'},
    {'q': '日头', 'locations': ['贵州'], 'regions': ['官话/西南']},
    {'q': '日头', 'locations': ['贵州'], 'standard_words': ['太阳']},
    {'q': '%', 'locations': ['贵州']}, {'q': '日_', 'locations': ['贵州']},
    {'q': '日头', 'locations': ['%']}, {'q': '日头', 'locations': ['贵_']},
    {'q': '日\0头', 'locations': ['贵州']}, {'q': '日头', 'locations': ['贵\0州']},
])
def test_entries_other_shapes_keep_automatic_count_plan(database, params):
    _, session, statements = database
    query.query_vocabulary_items(session=session, **params)
    count = next(s for s in statements if s.startswith('SELECT COUNT(*)'))
    assert 'INDEXED BY' not in count


@pytest.mark.parametrize('params', [
    {'q': '日头', 'locations': ['贵州']},
    {'q': '不存在', 'locations': ['贵州']},
])
def test_standard_words_default_fuzzy_location_uses_identity(database, params):
    _, session, statements = database
    result = query.query_vocabulary_standard_words(session=session, limit=None, **params)
    assert result.total == len(result.standard_words)
    sql = next(s for s in statements if s.startswith('SELECT'))
    assert 'INDEXED BY idx_vocabulary_entries_user_location' in sql


@pytest.mark.parametrize('params', [
    {'q': '共同', 'locations': ['贵州']}, {'q': '共同', 'locations': ['不存在地点']},
    {'q': '共同', 'locations': ['贵州', '孤立']},
    {'q': '共同', 'locations': ['%']}, {'q': '共同', 'locations': ['_']},
    {'q': '共同', 'locations': ['贵州'], 'province': '贵州'},
    {'q': '共同', 'locations': ['贵州'], 'regions': ['官话/西南']},
    {'q': '%', 'locations': ['贵州']},
])
def test_full_pagination_and_aggregation_equal_generic_plan(database, monkeypatch, params):
    conn, session, _ = database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa,notes) VALUES (?,?,?,?,?,?)',
        [(1 if i % 2 else 9, '同名' if i % 2 else '孤立地点', '太阳' if i % 3 else '太陽',
          '共同日头', 'aBc', '备注\0共同' if i % 3 else None) for i in range(257)])
    conn.commit()
    def collect():
        first = query.query_vocabulary_items(session=session, page_size=17, **params)
        pages = [asdict(first)]
        for page in range(2, (first.total + 16) // 17 + 2):
            pages.append(asdict(query.query_vocabulary_items(session=session, page_size=17, page=page, **params)))
        assert sum(len(p['items']) for p in pages) == first.total
        words = query.query_vocabulary_standard_words(session=session, limit=None, **params)
        assert words.total == len(words.standard_words)
        return pages, asdict(words)
    actual = collect()
    monkeypatch.setattr(query, '_prefer_location_identity_scan', lambda **kwargs: False)
    assert actual == collect()


def test_location_scope_plan_accepts_single_use_iterables(database):
    _, session, statements = database
    result = query.query_vocabulary_items(session=session, q='日头',
        search_fields=iter(['all']), locations=iter(['贵州']))
    assert result.total == 2
    count = next(s for s in statements if s.startswith('SELECT COUNT(*)'))
    assert 'INDEXED BY idx_vocabulary_entries_user_location' in count


def test_entries_location_scope_reuses_precise_count_across_all_pages(database):
    conn, session, _ = database
    counts, calls = {}, []
    def cached_count(sql, values):
        key = (sql, tuple(values))
        if key not in counts:
            calls.append(key)
            counts[key] = conn.execute(sql, values).fetchone()[0]
        return counts[key]
    pages = [query.query_vocabulary_items(session=session, q='日头', locations=['贵州'],
        page=page, page_size=1, _count_loader=cached_count) for page in range(1, 4)]
    assert [page.total for page in pages] == [2, 2, 2]
    assert [[item.id for item in page.items] for page in pages] == [[2], [1], []]
    assert len(calls) == 1


def test_entries_multi_location_keeps_generic_plan(database):
    _, session, statements = database
    query.query_vocabulary_items(session=session, q='日头', locations=['贵州', '广东'])
    count = next(s for s in statements if s.startswith('SELECT COUNT(*)'))
    assert 'INDEXED BY' not in count


@pytest.mark.parametrize('q,locations', [('新增', ['新增']), ('新', ['新增']), ('新增', ['新']), ('ABC', ['abc']), ('广东', ['廣東']), ('新增詞', ['新增词']), ('新增词', ['新增詞'])])
@pytest.mark.parametrize('endpoint', ['items', 'standard_words'])
def test_overlapping_keyword_and_scope_keeps_generic_plan(database, endpoint, q, locations):
    _, session, statements = database
    options = dict(q=q, locations=locations)
    if endpoint == 'standard_words':
        options['limit'] = None
    getattr(query, 'query_vocabulary_' + endpoint)(session=session, **options)
    sql = next(s for s in statements if s.startswith('SELECT'))
    assert 'INDEXED BY' not in sql
