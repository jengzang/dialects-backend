"""Optional search index: identical results, conservative boundaries, no startup DDL."""
from dataclasses import asdict
import sqlite3

import pytest

from app.service.vocabulary import query
from tests.test_vocabulary_query_resources import database

NAME = 'idx_vocabulary_entries_search_cover'
DDL = f'CREATE INDEX {NAME} ON vocabulary_entries(standard_word,location_name,local_expression,user_id)'


def aggregate(kind, session, **params):
    fn = query.query_vocabulary_standard_words if kind == 'standard' else query.query_vocabulary_map_points
    return fn(session=session, **params)


@pytest.mark.parametrize('kind', ['standard', 'map'])
@pytest.mark.parametrize('fields', [['headword'], ['definition'], ['headword', 'definition']])
@pytest.mark.parametrize('q', ['日', '太陽', '不存在', '共同', 'a'])
def test_covering_results_and_plans_equal_original(database, kind, fields, q):
    conn, session, statements = database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES (?,?,?,?,?)',
        [(i % 3 + 1, '同名' if i % 2 else '孤立地点', '太阳' if i % 2 else '太陽',
          '共同日头' if i % 5 else '太陽a', 'a') for i in range(303)])
    conn.commit()
    expected = asdict(aggregate(kind, session, q=q, search_fields=fields))
    original_sql = next(s for s in reversed(statements) if s.startswith('SELECT') and 'GROUP BY' in s)
    use_cover = kind == 'standard' or 'NOT INDEXED' in original_sql
    conn.execute(DDL)
    statements.clear()
    actual = asdict(aggregate(kind, session, q=q, search_fields=fields))
    assert actual == expected
    sql = next(s for s in reversed(statements) if s.startswith('SELECT') and 'GROUP BY' in s)
    assert (f'INDEXED BY {NAME}' in sql) is use_cover
    plan = conn.execute('EXPLAIN QUERY PLAN ' + sql).fetchall()
    if use_cover:
        assert any('USING COVERING INDEX ' + NAME in row[-1] for row in plan)
    assert not any(s.startswith(('CREATE', 'ANALYZE', 'VACUUM')) for s in statements)


@pytest.mark.parametrize('kind', ['standard', 'map'])
@pytest.mark.parametrize('options', [
    {'q': ''}, {'q': '%'}, {'q': '日_'}, {'q': '日\0头'},
    {'locations': ['贵州']}, {'province': '贵州'}, {'city': '广州'},
    {'regions': ['官话/西南']}, {'search_fields': ['all']},
    {'search_fields': ['headword', 'location']}, {'search_fields': ['detail']},
    {'search_fields': ['pronunciation']},
])
def test_cover_does_not_change_unmeasured_paths(database, kind, options):
    conn, session, statements = database
    params = dict(q='日头', search_fields=['definition', 'headword']); params.update(options)
    expected = asdict(aggregate(kind, session, **params))
    conn.execute(DDL); statements.clear()
    assert asdict(aggregate(kind, session, **params)) == expected
    assert not any(f'INDEXED BY {NAME}' in s for s in statements)


@pytest.mark.parametrize('definition', [
    None,
    f'CREATE INDEX {NAME} ON vocabulary_entries(standard_word)',
    DDL + " WHERE standard_word <> ''",
    f'CREATE UNIQUE INDEX {NAME} ON vocabulary_entries(id,standard_word,location_name,local_expression)',
    f'CREATE INDEX {NAME} ON vocabulary_entries(standard_word COLLATE NOCASE,location_name,local_expression,user_id)',
    f'CREATE INDEX {NAME} ON vocabulary_entries(standard_word DESC,location_name,local_expression,user_id)',
])
@pytest.mark.parametrize('kind', ['standard', 'map'])
def test_absent_or_incompatible_index_preserves_fallback(database, definition, kind):
    conn, session, statements = database
    expected = asdict(aggregate(kind, session, q='日头', search_fields=['headword']))
    if definition: conn.execute(definition)
    statements.clear()
    assert asdict(aggregate(kind, session, q='日头', search_fields=['headword'])) == expected
    assert not any(f'INDEXED BY {NAME}' in s for s in statements)


@pytest.mark.parametrize('kind', ['standard', 'map'])
def test_index_readiness_is_not_stale_after_drop_and_recreate(database, kind):
    conn, session, statements = database
    conn.execute(DDL)
    aggregate(kind, session, q='日头', search_fields=['headword'])
    assert any(f'INDEXED BY {NAME}' in s for s in statements)
    conn.execute(f'DROP INDEX {NAME}'); statements.clear()
    aggregate(kind, session, q='日头', search_fields=['headword'])
    assert not any(f'INDEXED BY {NAME}' in s for s in statements)
    conn.execute(DDL); statements.clear()
    aggregate(kind, session, q='日头', search_fields=['headword'])
    assert any(f'INDEXED BY {NAME}' in s for s in statements)


@pytest.mark.parametrize('kind', ['standard', 'map'])
def test_index_remains_current_after_writes(database, kind):
    conn, session, _ = database
    conn.execute(DDL)
    before = asdict(aggregate(kind, session, q='日头', search_fields=['headword']))
    conn.execute("UPDATE vocabulary_entries SET local_expression='别的' WHERE id=1")
    conn.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(2,'同名','新词','日头','a')")
    conn.commit()
    after = asdict(aggregate(kind, session, q='日头', search_fields=['headword']))
    conn.execute(f'DROP INDEX {NAME}')
    assert after == asdict(aggregate(kind, session, q='日头', search_fields=['headword']))
    assert after != before


@pytest.mark.parametrize('kind', ['standard', 'map'])
def test_concurrent_drop_after_probe_falls_back_once(database, monkeypatch, kind):
    conn, session, _ = database
    expected = asdict(aggregate(kind, session, q='日头', search_fields=['headword']))
    conn.execute(DDL)
    original = query._global_search_cover
    probes = []
    def drop_after_probe(cursor, **params):
        ready = original(cursor, **params)
        probes.append(ready)
        conn.execute(f'DROP INDEX {NAME}')
        return ready
    monkeypatch.setattr(query, '_global_search_cover', drop_after_probe)
    assert asdict(aggregate(kind, session, q='日头', search_fields=['headword'])) == expected
    assert probes == [True]


def test_other_sql_errors_are_not_retried():
    class Cursor:
        calls = 0
        def execute(self, sql, values):
            self.calls += 1
            raise sqlite3.OperationalError('interrupted')
    cursor = Cursor()
    with pytest.raises(sqlite3.OperationalError, match='interrupted'):
        query._execute_scoped_aggregate(None, cursor, q='日', fields=['headword'],
            locations=[], province=None, city=None, regions=[], select_sql='SELECT broken',
            values=[], columns='', scoped_select=None, fallback_sql='SELECT fallback')
    assert cursor.calls == 1
