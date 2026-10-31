"""Location-first counting must preserve exact totals and every result page."""
from dataclasses import asdict

import pytest

from app.service.vocabulary import query
from tests.test_vocabulary_query_resources import database


@pytest.mark.parametrize('terms', [
    ['同名'], ['贵州'], ['广东'], ['孤立'], ['不存在'],
    ['贵州', '同名', '孤立'], ['同', '同名'], ['%'], ['%%'], ['_'],
    ['贵%'], ['贵州', '%'], ['同名', '同名'], ['廣東'],
])
def test_location_first_count_preserves_all_pages(database, terms):
    conn, session, _ = database
    conn.execute('UPDATE vocabulary_locations SET county=NULL WHERE user_id=1')
    where, values = query._build_filter_clause(q=None, search_fields=None, locations=terms)
    join = ('LEFT JOIN vocabulary_locations l ON l.user_id=e.user_id '
            'AND l.location_name=e.location_name ') if 'l.' in where else ''
    original = 'SELECT COUNT(*) FROM vocabulary_entries e ' + join + 'WHERE ' + where
    sql, params = query._location_first_count_sql(terms, original, values)
    assert conn.execute(sql, params).fetchone()[0] == conn.execute(original, values).fetchone()[0]
    actual = []
    expected = []
    for page in range(1, 6):
        options = dict(session=session, locations=terms, page=page, page_size=1)
        actual.append(asdict(query.query_vocabulary_items(**options)))
        expected.append(asdict(query.query_vocabulary_items(
            **options, _count_loader=lambda *_: conn.execute(original, values).fetchone()[0])))
    assert actual == expected


@pytest.mark.parametrize('names', [0, 1, 255, 256, 257, 600])
def test_location_enumeration_bound_selects_fallback_without_losing_data(database, names):
    conn, _, _ = database
    conn.execute('DELETE FROM vocabulary_entries')
    conn.executemany('INSERT INTO vocabulary_entries '
        '(user_id,location_name,standard_word,local_expression,ipa) VALUES (?,?,?,?,?)',
        [(1, f'地点{i:04}', '词', '', '') for i in range(names)])
    calls = []
    conn.create_function('fallback', 0, lambda: calls.append(True) or names)
    sql, values = query._location_first_count_sql(['地点'], 'SELECT fallback() + ?', [0])
    assert conn.execute(sql, values).fetchone()[0] == names
    assert bool(calls) == (names > 256)


@pytest.mark.parametrize('options', [
    {'locations': ['贵州']}, {'q': '  ', 'locations': ['孤立']},
])
def test_entries_uses_location_first_count(database, options):
    conn, session, _ = database
    captured = []
    def load(sql, values):
        captured.append(sql)
        return conn.execute(sql, values).fetchone()[0]
    query.query_vocabulary_items(session=session, _count_loader=load, **options)
    assert 'WITH RECURSIVE' in captured[0]


@pytest.mark.parametrize('options', [
    {}, {'locations': ['贵州'], 'q': '太阳'},
    {'locations': ['贵州'], 'standard_words': ['太阳']},
    {'locations': ['贵州'], 'province': '贵州'},
    {'locations': ['贵州'], 'city': '贵阳'},
    {'locations': ['贵州'], 'regions': ['官话/西南']},
])
def test_other_count_paths_are_unchanged(database, options):
    conn, session, _ = database
    captured = []
    def load(sql, values):
        captured.append(sql)
        return conn.execute(sql, values).fetchone()[0]
    query.query_vocabulary_items(session=session, _count_loader=load, **options)
    assert 'WITH RECURSIVE' not in captured[0]


def test_many_location_terms_keep_original_parameter_budget(database):
    conn, _, _ = database
    terms = [f'地点{i}' for i in range(40)]
    where, values = query._build_filter_clause(q=None, search_fields=None, locations=terms)
    original = 'SELECT COUNT(*) FROM vocabulary_entries e WHERE ' + where
    sql, params = query._location_first_count_sql(terms, original, values)
    assert conn.execute(sql, params).fetchone()[0] == 0
    assert len(params) == len(values)


def test_name_and_metadata_overlap_across_users_and_orphans(database):
    conn, session, _ = database
    conn.executemany('INSERT INTO vocabulary_entries '
        '(user_id,location_name,standard_word,local_expression,ipa) VALUES (?,?,?,?,?)', [
            (3, '贵州', '词', '', ''), (4, '贵州', '词', '', ''),
            (5, '', '词', '', ''), (6, '廣州', '词', '', ''),
        ])
    conn.execute("INSERT INTO vocabulary_locations(user_id,location_name,coordinates,province) "
                 "VALUES (3,'贵州','','贵州')")
    for terms, expected in [(['贵州'], 4), (['贵州', '同名'], 5), (['%'], 8)]:
        result = query.query_vocabulary_items(session=session, locations=terms)
        assert result.total == expected
        assert len(result.items) == expected


def test_fallback_keeps_every_entry_available_across_pages(database):
    conn, session, _ = database
    conn.execute('DELETE FROM vocabulary_entries')
    conn.executemany('INSERT INTO vocabulary_entries '
        '(user_id,location_name,standard_word,local_expression,ipa) VALUES (?,?,?,?,?)',
        [(1, f'地点{i:04}', '词', '', '') for i in range(600)])
    rows = []
    for page in range(1, 5):
        result = query.query_vocabulary_items(
            session=session, locations=['地点'], page_size=200, page=page)
        assert result.total == 600
        rows.extend(item.id for item in result.items)
    assert len(rows) == len(set(rows)) == 600
    assert rows == sorted(rows, reverse=True)
