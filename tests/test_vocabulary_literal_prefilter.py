"""Literal acceleration must preserve SQLite LIKE, totals and lazy-cache semantics."""
import sqlite3
from dataclasses import asdict

import pytest

from app.service.vocabulary import query
from tests.test_vocabulary_query_resources import database


def test_global_short_page_infers_exact_total(database):
    _, session, sql = database
    result = query.query_vocabulary_items(session=session, q='日头', search_fields=['headword'])
    assert result.total == 2 and [i.id for i in result.items] == [2, 1]
    assert not any(s.startswith('SELECT COUNT(*)') for s in sql)


def test_sparse_global_uses_guarded_prefilter(database):
    conn, session, sql = database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
        [(1, '同名', '普通', '别的', '') for _ in range(4096)])
    conn.commit(); sql.clear()
    result = query.query_vocabulary_items(session=session, q='日头', search_fields=['headword'])
    assert result.total == 2
    assert any('instr(e.local_expression,' in s and ' LIKE ' in s for s in sql)
    probes = [s for s in sql if 'vocabulary_literal_probe' in s]
    assert 1 <= len(probes) <= 9
    assert all('LIMIT 16' in s or 'MIN(id)' in s for s in probes)


def fill(conn, *, word='别的', count=4096):
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa,notes,informations) VALUES(?,?,?,?,?,?,?)',
        [(1, '同名', '普通', word, 'a', None, '') for _ in range(count)])
    conn.commit()


@pytest.mark.parametrize('fields', [['definition'], ['headword'], ['definition', 'headword'],
    ['all'], ['pronunciation'], ['detail'], ['headword', 'detail']])
@pytest.mark.parametrize('word', ['日头', '无命中', 'a', '%', '_', '日\x00头', '  日头  '])
def test_accelerated_results_equal_original_like_for_all_fields(database, fields, word):
    conn, session, sql = database
    fill(conn)
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa,notes,informations) VALUES(?,?,?,?,?,?,?)', [
        (9, '孤立地点', '太阳', '日头\x00后缀', 'a', None, '日头'),
        (1, '同名', '太陽', '前\x00日头', 'A', '备注', None),
        (1, '同名', '日头', sqlite3.Binary('日头'.encode()), 'a', '', ''),
    ])
    conn.commit()
    options = dict(session=session, q=word, search_fields=fields, page_size=2)
    expected = query.query_vocabulary_items(**options,
        _count_loader=lambda statement, bindings: conn.execute(statement, bindings).fetchone()[0])
    actual = query.query_vocabulary_items(**options)
    assert asdict(actual) == asdict(expected)


@pytest.mark.parametrize('word', ['日头', '前缀日头后缀'])
def test_dense_sample_retains_original_like(database, word):
    conn, session, sql = database
    fill(conn, word=word)
    sql.clear()
    result = query.query_vocabulary_items(session=session, q='日头', search_fields=['headword'])
    assert result.total == 4098 and len(result.items) == 50
    assert not any('instr(' in s for s in sql)
    assert len([s for s in sql if 'vocabulary_literal_probe' in s]) <= 9


def test_distributed_probe_detects_old_dense_rows_not_only_recent(database):
    conn, session, sql = database
    fill(conn, word='日头', count=2048)
    fill(conn, count=2048)
    sql.clear()
    result = query.query_vocabulary_items(session=session, q='日头', search_fields=['headword'])
    assert result.total == 2050
    assert not any('instr(' in s for s in sql)


@pytest.mark.parametrize('params', [
    {'q':'ABC'}, {'q':'日头a'}, {'q':'%'}, {'q':'_'}, {'q':'日\x00头'},
    {'q':None}, {'province':'贵州'}, {'regions':['官话/西南']},
    {'standard_words':['太阳']}, {'search_fields':['location']}, {'page':2},
])
def test_unsafe_or_unmeasured_modes_do_not_probe(database, params):
    conn, session, sql = database
    fill(conn);sql.clear()
    options = dict(q='日头', search_fields=['headword']);options.update(params)
    query.query_vocabulary_items(session=session, **options)
    assert not any('vocabulary_literal_probe' in s for s in sql)


@pytest.mark.parametrize('cached_total', [0,2])
def test_count_hit_skips_planning_and_preserves_signature(database, cached_total):
    conn, session, sql = database
    fill(conn);sql.clear();keys=[]
    def hit(statement, bindings, compute):
        keys.append((statement, tuple(bindings)));return cached_total
    options=dict(session=session,q='日头',search_fields=['headword'])
    result=query.query_vocabulary_items(**options,_count_resolver=hit)
    assert not any('vocabulary_literal_probe' in s for s in sql)
    def miss(statement, bindings, compute):
        keys.append((statement, tuple(bindings)));return compute()
    query.query_vocabulary_items(**options,_count_resolver=miss)
    assert keys[0]==keys[1]
    assert result.total==cached_total


def test_global_count_and_page_use_same_snapshot(database):
    conn, session, sql = database
    conn.execute('PRAGMA journal_mode=WAL')
    fill(conn)
    wrote=False
    with sqlite3.connect(conn.execute('PRAGMA database_list').fetchone()[2]) as writer:
        def trace(statement):
            nonlocal wrote
            sql.append(statement)
            if 'vocabulary_literal_probe' in statement and 'LIMIT 16' in statement and not wrote:
                writer.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(1,'同名','太阳','日头','z')")
                writer.commit();wrote=True
        conn.set_trace_callback(trace)
        result=query.query_vocabulary_items(session=session,q='日头',search_fields=['headword'],page_size=1)
    assert wrote and result.total==2 and result.items[0].id==2
    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM vocabulary_entries WHERE local_expression LIKE '%日头%'").fetchone()[0]==2  # 日頭 is matched by script expansion, not this literal


@pytest.mark.parametrize('caller_transaction',[False,True])
def test_prefilter_failure_releases_savepoint(database, caller_transaction):
    conn, session, _=database
    fill(conn)
    if caller_transaction:
        conn.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(1,'同名','临时','日头','')")
    conn.set_authorizer(lambda action, first, second, *_: sqlite3.SQLITE_DENY
                        if action==sqlite3.SQLITE_FUNCTION and second=='instr' else sqlite3.SQLITE_OK)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            query.query_vocabulary_items(session=session,q='日头',search_fields=['headword'])
    finally:
        conn.set_authorizer(None)
    assert conn.in_transaction==caller_transaction
    conn.rollback()


def test_wide_scope_prefilter_preserves_names_metadata_users_and_all_pages(database):
    conn, session, sql=database
    fill(conn)
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
        [(i%3+1,'同名','太阳','日头','') for i in range(160)])
    conn.commit()
    options=dict(session=session,q='日头',locations=['同名','孤立'],search_fields=['headword'],page_size=50)
    expected=query.query_vocabulary_items(**options,_count_loader=lambda s,v:conn.execute(s,v).fetchone()[0])
    actual=query.query_vocabulary_items(**options)
    assert actual==expected and actual.total==162
    assert any('instr(' in s for s in sql)
    ids=[]
    for page in range(1,5):ids.extend(i.id for i in query.query_vocabulary_items(**options,page=page).items)
    assert len(ids)==len(set(ids))==actual.total and ids==sorted(ids,reverse=True)


@pytest.mark.parametrize('matches,enabled', [(8,True),(9,False)])
def test_literal_sample_density_threshold(database, matches, enabled):
    conn, session, sql=database
    fill(conn)
    low,high=conn.execute('SELECT MIN(id),MAX(id) FROM vocabulary_entries').fetchone()
    ids=[low+(high-low)*block//8 for block in range(8)]
    if matches==9:ids.append(low+1)
    conn.executemany("UPDATE vocabulary_entries SET local_expression='共同' WHERE id=?",[(i,) for i in ids])
    conn.commit();sql.clear()
    result=query.query_vocabulary_items(session=session,q='共同',search_fields=['headword'])
    assert result.total==matches
    assert any('instr(' in s for s in sql)==enabled


def test_empty_database_has_no_prefilter_and_exact_zero(database):
    conn,session,sql=database
    conn.execute('DELETE FROM vocabulary_entries');conn.commit();sql.clear()
    result=query.query_vocabulary_items(session=session,q='共同',search_fields=['headword'])
    assert result.total==0 and result.items==[]
    assert not any('instr(' in s for s in sql)


def test_legacy_count_loader_does_not_probe(database):
    conn,session,sql=database
    fill(conn);sql.clear()
    result=query.query_vocabulary_items(session=session,q='日头',search_fields=['headword'],
        _count_loader=lambda s,v:conn.execute(s,v).fetchone()[0])
    assert result.total==2
    assert not any('vocabulary_literal_probe' in s for s in sql)


def test_dense_global_keeps_count_before_page_to_avoid_cold_double_reads(database):
    conn,session,sql=database
    fill(conn,word='日头',count=2048);fill(conn,count=2048);sql.clear()
    result=query.query_vocabulary_items(session=session,q='日头',search_fields=['headword'])
    assert result.total==2050
    main=[s for s in sql if s.startswith('SELECT') and 'vocabulary_literal_probe' not in s]
    assert main[0].startswith('SELECT COUNT(*)')


def test_single_character_search_keeps_original_plan(database):
    conn,session,sql=database
    fill(conn);sql.clear()
    result=query.query_vocabulary_items(session=session,q='日',search_fields=['headword'])
    assert result.total==2
    assert not any('vocabulary_literal_probe' in s for s in sql)
    assert not any('instr(' in s for s in sql)
