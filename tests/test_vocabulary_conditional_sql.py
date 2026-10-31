"""Query-path regression tests; complete semantics also exercised against legacy LIKE."""
from dataclasses import asdict

import pytest

from tests.test_vocabulary_query_resources import database
from app.service.vocabulary import query


@pytest.mark.parametrize('params', [
    {'q': '日'},
    {'q': '日', 'search_fields': ['headword']},
    {'q': 'a', 'search_fields': ['pronunciation']},
    {'q': '备注', 'search_fields': ['detail']},
])
def test_standard_words_scans_table_for_unscoped_noncovering_search(database, params):
    _, session, statements = database
    query.query_vocabulary_standard_words(session=session, limit=None, **params)
    sql = next(sql for sql in statements if sql.startswith('SELECT'))
    assert 'FROM vocabulary_entries e NOT INDEXED ' in sql


@pytest.mark.parametrize('params', [
    {}, {'q': '  '},
    {'q': '太阳', 'search_fields': ['definition']},
    {'q': '太阳', 'search_fields': iter(['definition'])},
    {'q': '日', 'locations': ['广东']},
    {'q': '日', 'province': '贵州'},
    {'q': '日', 'city': '贵阳'},
    {'q': '日', 'regions': ['官话/西南']},
    {'q': '日', 'search_fields': ['headword', 'location']},
    {'q': '%'}, {'q': '_'}, {'q': '日%'},
])
def test_standard_words_keeps_existing_plan_for_other_shapes(database, params):
    _, session, statements = database
    query.query_vocabulary_standard_words(session=session, limit=None, **params)
    sql = next(sql for sql in statements if sql.startswith('SELECT'))
    assert 'NOT INDEXED' not in sql
    if params.get('regions'):
        assert 'INDEXED BY idx_vocabulary_entries_user_location' in sql


@pytest.mark.parametrize('endpoint', ['items', 'standard_words', 'map_points', 'map_items'])
@pytest.mark.parametrize('params', [
    {'q': '广州', 'search_fields': ['location']},
    {'q': '广州', 'search_fields': ['headword', 'location']},
    {'locations': ['广东', '贵州']},
])
def test_location_text_is_prefiltered_without_per_entry_metadata_join(database, endpoint, params):
    _, session, statements = database
    options = dict(params)
    if endpoint == 'map_items':
        options['standard_words'] = ['太阳']
    getattr(query, 'query_vocabulary_' + endpoint)(session=session, **options)
    selects = [sql for sql in statements if sql.startswith(('SELECT', 'WITH RECURSIVE'))]
    assert any('SELECT p.user_id, p.location_name FROM vocabulary_locations p WHERE' in sql
               for sql in selects)
    if endpoint == 'items':
        count_sql = next(sql for sql in selects if sql.startswith(('SELECT COUNT(*)', 'WITH RECURSIVE')))
        assert 'LEFT JOIN' not in count_sql


@pytest.mark.parametrize('params', [
    {'q': '广州', 'search_fields': ['location'], 'province': '广东'},
    {'locations': ['广东'], 'city': '广州'},
    {'locations': ['广东'], 'regions': ['粤语/广府']},
    {'q': '%', 'search_fields': ['location']},
    {'locations': ['%%', '广东']},
])
def test_location_prefilter_falls_back_for_constraints_or_empty_matching_patterns(database, params):
    _, session, statements = database
    query.query_vocabulary_items(session=session, **params)
    count_sql = next(sql for sql in statements if sql.startswith(('SELECT COUNT(*)', 'WITH RECURSIVE')))
    assert 'LEFT JOIN vocabulary_locations l' in count_sql


@pytest.mark.parametrize('endpoint', ['items', 'standard_words', 'map_points', 'map_items'])
@pytest.mark.parametrize('params', [
    {}, {'q': '日'}, {'q': '太陽'},
    {'q': '广州', 'search_fields': ['headword', 'location']},
    {'q': '%', 'search_fields': ['location']},
    {'q': '%%', 'search_fields': ['detail', 'location']},
    {'q': '_', 'search_fields': ['location']},
    {'q': '不存在', 'search_fields': ['location']},
    {'locations': ['孤立']}, {'locations': ['%']},
    {'locations': ['广东', '孤立']},
    {'q': '日', 'locations': ['贵州']},
    {'q': '日', 'province': '贵州', 'locations': ['贵阳']},
    {'q': '日', 'regions': ['官话/西南'], 'locations': ['贵阳']},
    {'province': '广东', 'city': '不存在'},
])
def test_complete_result_equals_legacy_like_with_nulls_and_orphans(database, monkeypatch, endpoint, params):
    conn, session, _ = database
    conn.execute('UPDATE vocabulary_locations SET county=NULL WHERE user_id=1')
    conn.execute('UPDATE vocabulary_entries SET notes=NULL, informations=NULL WHERE user_id=1')
    options = dict(params)
    if endpoint == 'standard_words':
        options['limit'] = None
    elif endpoint == 'map_items':
        options['standard_words'] = ['太阳', '月亮']
    function = getattr(query, 'query_vocabulary_' + endpoint)
    actual = function(session=session, **options)
    def legacy_like(*, clauses, values, columns, terms, prefilter_locations=False):
        return query._append_like_group(clauses=clauses, values=values,
                                        columns=columns, terms=terms)
    monkeypatch.setattr(query, '_append_search_like_group', legacy_like)
    expected = function(session=session, **options)
    assert asdict(actual) == asdict(expected)
