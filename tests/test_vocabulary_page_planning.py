"""Page planning remains useful when counts are cached or pages advance."""
import sqlite3

import pytest

from app.service.vocabulary import query
from app.service.vocabulary.scope_plan import plan_location_scope
from tests.test_vocabulary_query_resources import database


PARAMS = dict(q='日头', search_fields=['headword'], locations=['贵州'])


def scope_reads(sql):
    return [s for s in sql if 'vocabulary_scope_plan' in s]


@pytest.mark.parametrize('page', [1, 2])
@pytest.mark.parametrize('count_hit', [False, True])
def test_each_page_plans_independently_of_count_cache(database, page, count_hit):
    conn, session, sql = database
    expected = query.query_vocabulary_items(session=session, **PARAMS, page=page, page_size=1,
        _count_loader=lambda statement, values: conn.execute(statement, values).fetchone()[0])
    sql.clear()
    def resolve(statement, values, compute):
        return expected.total if count_hit else compute()
    actual = query.query_vocabulary_items(session=session, **PARAMS, page=page, page_size=1,
        _count_resolver=resolve)
    assert actual == expected
    assert scope_reads(sql), 'page planning must not depend on count miss or first page'
    assert any('CROSS JOIN vocabulary_entries' in s and 'vocabulary_scope_plan' not in s for s in sql)
    if count_hit:
        assert not any('vocabulary_scope_count' in s for s in sql)


@pytest.mark.parametrize('total,page', [(0, 1), (2, 3)])
def test_cached_empty_or_out_of_range_does_no_planning(database, total, page):
    _, session, sql = database
    result = query.query_vocabulary_items(session=session, **PARAMS, page=page, page_size=1,
        _count_resolver=lambda statement, values, compute: total)
    assert result.total == total and result.items == []
    assert not scope_reads(sql)
    assert not any(s.startswith(('SELECT', 'WITH')) for s in sql)


@pytest.mark.parametrize('analyzed', [False, True])
def test_scope_planning_never_counts_whole_entries_table(database, analyzed):
    conn, session, sql = database
    if analyzed:
        conn.execute('ANALYZE'); conn.commit()
    sql.clear()
    result = query.query_vocabulary_items(session=session, **PARAMS)
    assert result.total == 2
    assert not any('SELECT /* vocabulary_scope_plan */ COUNT(*) FROM vocabulary_entries' in s for s in sql)
    if not analyzed:
        probes = [s for s in scope_reads(sql) if 'LIMIT 4097' in s]
        assert len(probes) == 1, 'missing statistics may only use a bounded size probe'


def fill_scope(conn, count, outside=0):
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
        ((1, '同名', '太阳', '日头', '') for _ in range(count)))
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
        ((1, '范围外', '无关', '无关', '') for _ in range(outside)))
    conn.commit()


def test_entries_use_selective_scope_above_old_ten_percent_budget(database):
    conn, session, sql = database
    fill_scope(conn, 1500, outside=10000)
    conn.execute('ANALYZE'); conn.commit(); sql.clear()
    result = query.query_vocabulary_items(session=session, **PARAMS, page=2, page_size=200)
    assert result.total == 1502 and len(result.items) == 200
    assert any('CROSS JOIN vocabulary_entries' in s and 'vocabulary_scope_plan' not in s for s in sql)


@pytest.mark.parametrize('extra,accept', [(6, True), (7, False)])
def test_candidate_probe_stops_at_cap_plus_one(database, extra, accept):
    conn, _, sql = database
    fill_scope(conn, extra)
    sql.clear()
    scope = plan_location_scope(conn.cursor(), locations=['贵州'], metadata_columns=['p.province'],
        max_candidates=8, coverage_divisor=4)
    assert (scope is not None) == accept
    probes = [s for s in scope_reads(sql) if 'SELECT 1 FROM' in s or "SELECT 1 " in s]
    assert any('LIMIT 9' in s for s in probes)


@pytest.mark.parametrize('stat', ['1 1', 'invalid', None])
def test_stale_or_invalid_stats_do_not_change_results(database, stat):
    conn, session, _ = database
    fill_scope(conn, 1500, outside=10000)
    conn.execute('ANALYZE')
    conn.execute("UPDATE sqlite_stat1 SET stat=? WHERE tbl='vocabulary_entries' AND idx='ix_vocabulary_entries_location_name'", (stat,))
    conn.commit()
    expected = query.query_vocabulary_items(session=session, **PARAMS, page=2, page_size=200,
        _count_loader=lambda statement, values: conn.execute(statement, values).fetchone()[0])
    assert query.query_vocabulary_items(session=session, **PARAMS, page=2, page_size=200) == expected


@pytest.mark.parametrize('page', [1, 2])
def test_cached_count_scope_and_page_share_snapshot(database, page):
    conn, session, sql = database
    conn.execute('PRAGMA journal_mode=WAL')
    wrote = False
    path = conn.execute('PRAGMA database_list').fetchone()[2]
    with sqlite3.connect(path) as writer:
        def trace(statement):
            nonlocal wrote
            sql.append(statement)
            if 'vocabulary_scope_plan' in statement and 'vocabulary_locations p' in statement and not wrote:
                writer.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(1,'同名','太阳','日头','z')")
                writer.commit(); wrote = True
        conn.set_trace_callback(trace)
        result = query.query_vocabulary_items(session=session, **PARAMS, page=page, page_size=1,
            _count_resolver=lambda statement, values, compute: 2)
    assert wrote and result.total == 2
    assert [i.id for i in result.items] == ([2] if page == 1 else [1])
    assert not conn.in_transaction
    assert conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0] == 5


def test_obviously_wide_estimated_scope_skips_candidate_walk(database):
    conn, session, sql = database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
        ((1, f'范围{i:02}', '太阳', '日头', '') for i in range(21) for _ in range(100)))
    fill_scope(conn, 0, outside=2000)
    conn.execute('ANALYZE'); conn.commit(); sql.clear()
    result = query.query_vocabulary_items(session=session, q='日头', locations=['范围'], search_fields=['headword'])
    assert result.total == 2100  # 范围外 matches locations but not the keyword.
    assert scope_reads(sql)
    assert not any('vocabulary_scope_plan' in s and 'CROSS JOIN vocabulary_entries' in s for s in sql)


def test_entries_candidate_walk_has_absolute_limit(database):
    conn, session, sql = database
    conn.execute('ANALYZE')
    conn.execute("UPDATE sqlite_stat1 SET stat='1000000 1' WHERE tbl='vocabulary_entries' AND idx='ix_vocabulary_entries_location_name'")
    conn.commit(); sql.clear()
    assert query.query_vocabulary_items(session=session, **PARAMS).total == 2
    assert any('vocabulary_scope_plan' in s and 'LIMIT 65537' in s for s in sql)


@pytest.mark.parametrize('total,limit', [(4096, 1025), (4097, 32769)])
def test_missing_statistics_probe_boundary_stays_bounded(database, total, limit):
    conn, _, sql = database
    fill_scope(conn, total - 4)
    sql.clear()
    plan_location_scope(conn.cursor(), locations=['贵州'], metadata_columns=['p.province'],
        max_candidates=65536, coverage_divisor=4)
    assert any('vocabulary_scope_plan' in s and 'LIMIT 4097' in s for s in sql)
    assert any('vocabulary_scope_plan' in s and 'CROSS JOIN vocabulary_entries' in s
               and f'LIMIT {limit}' in s for s in sql)


@pytest.mark.parametrize('caller_transaction', [False, True])
@pytest.mark.parametrize('failure', ['planning', 'page'])
def test_count_hit_failure_releases_only_own_savepoint(database, caller_transaction, failure):
    conn, session, _ = database
    if caller_transaction:
        conn.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(1,'同名','太阳','日头','z')")
    def authorize(action, table, column, *_):
        if action == sqlite3.SQLITE_READ:
            if failure == 'planning' and table == 'vocabulary_locations':
                return sqlite3.SQLITE_DENY
            if failure == 'page' and table == 'vocabulary_entries' and column == 'id':
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    conn.set_authorizer(authorize)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            query.query_vocabulary_items(session=session, **PARAMS, page=2, page_size=1,
                _count_resolver=lambda statement, values, compute: 2)
    finally:
        conn.set_authorizer(None)
    assert conn.in_transaction == caller_transaction
    conn.rollback()
    assert conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0] == 4


def test_cached_later_pages_deduplicate_names_metadata_and_preserve_orphans(database):
    conn, session, sql = database
    conn.execute("INSERT INTO vocabulary_locations(user_id,location_name,coordinates,province) VALUES(3,'元数据命中','106,27','贵州')")
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)', [
        (2, '同名', '太阳', '日头', ''), (9, '孤立地点', '太阳', '日头', ''),
        (3, '元数据命中', '太阳', '日头', ''), (9, '同名', '太阳', '日头', ''),
    ])
    conn.commit()
    params = dict(PARAMS, locations=['同名', '贵州', '孤立'])
    ids = []
    for page in range(1, 5):
        expected = query.query_vocabulary_items(session=session, **params, page=page, page_size=2,
            _count_loader=lambda statement, values: conn.execute(statement, values).fetchone()[0])
        sql.clear()
        actual = query.query_vocabulary_items(session=session, **params, page=page, page_size=2,
            _count_resolver=lambda statement, values, compute: 6)
        assert actual == expected and actual.total == 6
        ids.extend(i.id for i in actual.items)
        assert bool(scope_reads(sql)) == (page < 4)
    assert len(ids) == len(set(ids)) == 6 and ids == sorted(ids, reverse=True)
