"""Bounded scope planning preserves exact results and avoids cached-page regressions."""
import sqlite3

import pytest

from app.service.vocabulary import query
from tests.test_vocabulary_query_resources import database


PARAMS=dict(q='日头',search_fields=['definition','headword'],locations=['贵州','孤立'])


def planned(statements):
    return [s for s in statements if 'vocabulary_scope_plan' in s]


@pytest.mark.parametrize('fields',[['definition'],['headword'],['definition','headword']])
def test_entries_cold_scope_seeks_existing_indexes_and_exact_total(database,fields):
    _,session,sql=database
    result=query.query_vocabulary_items(session=session,q='太阳',search_fields=fields,
        locations=['贵州','孤立'],page_size=1)
    assert planned(sql), 'cold scoped request must use bounded scope planning'
    main=[s for s in sql if 'vocabulary_scope_plan' not in s]
    assert any('CROSS JOIN vocabulary_entries' in s for s in main)
    assert any('ix_vocabulary_entries_location_name' in s for s in main)
    if fields!=['headword']:
        assert result.total==2
        assert [i.id for i in result.items]==[2]
    else:
        assert result.total==0 and result.items==[]


def test_entries_count_hit_does_not_probe_or_change_cache_signature(database,monkeypatch):
    _,session,sql=database
    keys=[]
    def hit(statement,values,compute):
        keys.append((statement,tuple(values)))
        return 2
    actual=query.query_vocabulary_items(session=session,**PARAMS,_count_resolver=hit)
    assert not planned(sql)
    assert [i.id for i in actual.items]==[2,1]
    def miss(statement,values,compute):
        keys.append((statement,tuple(values)))
        return compute()
    sql.clear()
    cold=query.query_vocabulary_items(session=session,**PARAMS,_count_resolver=miss)
    assert planned(sql)
    assert keys[0]==keys[1]
    assert actual==cold


def test_legacy_count_loader_and_later_pages_keep_original_path(database):
    _,session,sql=database
    query.query_vocabulary_items(session=session,**PARAMS,_count_loader=lambda *_:2)
    assert not planned(sql)
    sql.clear()
    query.query_vocabulary_items(session=session,**PARAMS,page=2,page_size=1)
    assert not planned(sql)


@pytest.mark.parametrize('options',[
    {'q':None},{'q':'%'},{'q':'贵_州'},{'locations':['%']},{'locations':[]},
    {'search_fields':['all']},{'search_fields':['location','headword']},
    {'search_fields':['detail']},{'province':'贵州'},{'regions':['官话/西南']},
    {'standard_words':['太阳']},
])
def test_entries_unsupported_filters_never_probe(database,options):
    _,session,sql=database
    params=dict(PARAMS);params.update(options)
    query.query_vocabulary_items(session=session,**params)
    assert not planned(sql)


@pytest.mark.parametrize('kind',['names','identities','broad'])
def test_planning_budget_falls_back_without_truncating_entries(database,kind):
    conn,session,sql=database
    if kind=='names':
        rows=[(1,f'AAA{i:03}','太阳','日头','a') for i in range(257)]
        locations=['AAA','贵州']
    elif kind=='identities':
        conn.executemany('INSERT INTO vocabulary_locations(user_id,location_name,coordinates,province) VALUES(?,?,?,?)',
            [(i+100,'同名','106,27','贵州') for i in range(257)])
        rows=[(i+100,'同名','太阳','日头','a') for i in range(257)]
        locations=['贵州']
    else:
        rows=[(1,'同名','太阳','日头','a') for _ in range(3000)]
        locations=['贵州']
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',rows)
    conn.commit();sql.clear()
    result=query.query_vocabulary_items(session=session,q='日头',search_fields=['headword'],locations=locations,page_size=200)
    assert planned(sql)
    assert not any('CROSS JOIN vocabulary_entries' in s and 'vocabulary_scope_plan' not in s for s in sql)
    assert result.total==len(rows)+2
    all_ids=[]
    for page in range(1,(result.total+199)//200+1):
        all_ids.extend(i.id for i in query.query_vocabulary_items(session=session,q='日头',search_fields=['headword'],locations=locations,page_size=200,page=page).items)
    assert len(all_ids)==result.total==len(set(all_ids))
    assert all_ids==sorted(all_ids,reverse=True)


def test_scope_probe_page_and_count_share_wal_snapshot(database):
    conn,session,sql=database
    conn.execute('PRAGMA journal_mode=WAL')
    wrote=False
    with sqlite3.connect(conn.execute('PRAGMA database_list').fetchone()[2]) as writer:
        def trace(statement):
            nonlocal wrote
            sql.append(statement)
            if 'vocabulary_scope_plan' in statement and 'vocabulary_locations p' in statement and not wrote:
                writer.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(1,'同名','太阳','日头','z')")
                writer.commit();wrote=True
        conn.set_trace_callback(trace)
        result=query.query_vocabulary_items(session=session,**PARAMS,page_size=1)
    assert wrote
    assert result.total==2 and [i.id for i in result.items]==[2]
    assert not conn.in_transaction
    assert conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0]==5


@pytest.mark.parametrize('terms,expected',[(32,True),(33,False)])
def test_location_parameter_budget_boundary(database,terms,expected):
    _,session,sql=database
    result=query.query_vocabulary_items(session=session,**dict(PARAMS,locations=['贵州']*terms))
    assert result.total==2
    assert bool(planned(sql))==expected


@pytest.mark.parametrize('caller_transaction',[False,True])
def test_planning_error_preserves_callers_transaction(database,caller_transaction):
    conn,session,_=database
    if caller_transaction:
        conn.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(1,'同名','太阳','日头','z')")
    conn.set_authorizer(lambda action,table,*_:sqlite3.SQLITE_DENY
                        if action==sqlite3.SQLITE_READ and table=='vocabulary_locations' else sqlite3.SQLITE_OK)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            query.query_vocabulary_items(session=session,**PARAMS)
    finally:
        conn.set_authorizer(None)
    assert conn.in_transaction==caller_transaction
    conn.rollback()
    assert conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0]==4
