"""Unscoped ordinary map content searches and conservative plan boundaries."""
from dataclasses import asdict

import pytest

from app.service.vocabulary import query
from tests.test_vocabulary_query_resources import database


@pytest.mark.parametrize('fields', [['definition'], ['headword'], ['definition', 'headword']])
def test_literal_unscoped_map_content_scans_table(database, fields):
    _, session, statements = database
    query.query_vocabulary_map_points(session=session, q='日头', search_fields=fields)
    sql = [s for s in statements if s.startswith('SELECT')][-1]
    assert 'FROM vocabulary_entries e NOT INDEXED' in sql


@pytest.mark.parametrize('options', [
    {'q': ''}, {'q': '%'}, {'q': '日_'}, {'q': '日\0头'},
    {'locations': ['贵州']}, {'locations': ['贵州', '广东']},
    {'locations': ['不存在']}, {'province': '贵州'}, {'city': '贵阳'},
    {'regions': ['官话/西南']}, {'search_fields': ['location']},
    {'search_fields': ['headword', 'location']}, {'search_fields': ['all']},
    {'search_fields': ['detail']}, {'search_fields': ['pronunciation']},
])
def test_unmeasured_scoped_or_wildcard_paths_keep_existing_plan(database, options):
    _, session, statements = database
    params = dict(q='日头', search_fields=['definition', 'headword'])
    params.update(options)
    query.query_vocabulary_map_points(session=session, **params)
    assert 'NOT INDEXED' not in next(s for s in statements if s.startswith('SELECT'))


@pytest.mark.parametrize('q', ['日头', '太陽', '不存在', '共同'])
def test_map_table_scan_preserves_full_counts_coordinates_and_order(database, q):
    conn, session, _ = database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES (?,?,?,?,?)',
        [(i % 3 + 1, '同名' if i % 2 else '孤立地点', '太阳' if i % 2 else '太陽', '共同日头', 'a')
         for i in range(223)])
    conn.commit()
    actual = query.query_vocabulary_map_points(session=session, q=q, search_fields=['definition', 'headword'])
    # Force the original SQL traversal while retaining the exact predicates.
    class Cursor:
        def __init__(self):
            self.inner = conn.cursor()
        def execute(self, sql, values):
            return self.inner.execute(sql.replace(' e NOT INDEXED ', ' e '), values)
        @property
        def description(self):
            return self.inner.description
        def fetchall(self):
            return self.inner.fetchall()
    from types import SimpleNamespace
    original_session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=SimpleNamespace(cursor=Cursor)))
    expected = query.query_vocabulary_map_points(session=original_session, q=q, search_fields=['definition', 'headword'])
    assert asdict(actual) == asdict(expected)


def test_map_scan_accepts_one_shot_search_iterables(database):
    _, session, statements = database
    result = query.query_vocabulary_map_points(session=session, q='日头',
        search_fields=iter(['headword']), locations=iter([]))
    assert result.total_entries == 2
    assert result.total_points == 1
    assert 'NOT INDEXED' in [s for s in statements if s.startswith('SELECT')][-1]


def test_dense_literal_keyword_retains_grouping_index_without_capping_results(database):
    conn, session, statements = database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES (?,?,?,?,?)',
        [(1 if i % 2 else 2, '同名', '共同太阳', '共同日头', 'a') for i in range(401)])
    conn.commit()
    result = query.query_vocabulary_map_points(session=session, q='共同', search_fields=['definition', 'headword'])
    assert result.total_entries == 401
    assert sum(point.entry_count for point in result.points) == 401
    main = [s for s in statements if s.startswith('SELECT')][-1]
    assert 'NOT INDEXED' not in main
    probes = [s for s in statements if 'LIMIT 128' in s]
    assert len(probes) == 1


@pytest.mark.parametrize('matches,scan', [(95, True), (96, False)])
def test_map_density_threshold_uses_only_recent_bounded_sample(database, matches, scan):
    conn, session, statements = database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES (?,?,?,?,?)',
        [(1, '同名', '共同' if i < matches else '别的', '方言', 'a') for i in range(128)])
    conn.commit()
    result = query.query_vocabulary_map_points(session=session, q='共同', search_fields=['definition'])
    assert result.total_entries == matches
    main = [s for s in statements if s.startswith('SELECT')][-1]
    assert ('NOT INDEXED' in main) is scan


def test_map_density_probe_handles_empty_database(database):
    conn, session, _ = database
    conn.execute('DELETE FROM vocabulary_entries')
    conn.commit()
    result = query.query_vocabulary_map_points(session=session, q='共同', search_fields=['headword'])
    assert result.total_entries == result.total_points == result.omitted_without_coordinates == 0
