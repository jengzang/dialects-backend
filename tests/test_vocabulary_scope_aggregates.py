"""Full aggregate equivalence on bounded scope plans."""
import pytest
from app.service.vocabulary import query
from tests.test_vocabulary_query_resources import database
from tests.test_vocabulary_scope_plan import PARAMS, planned


@pytest.mark.parametrize('endpoint',['standard','map'])
@pytest.mark.parametrize('qvalue',['日头','太阳','无命中'])
def test_aggregate_scope_result_equals_original(database,monkeypatch,endpoint,qvalue):
    _,session,sql=database
    func=query.query_vocabulary_standard_words if endpoint=='standard' else query.query_vocabulary_map_points
    params=dict(session=session,**dict(PARAMS,q=qvalue))
    if endpoint=='standard':params['limit']=None
    actual=func(**params)
    assert planned(sql)
    assert any('CROSS JOIN vocabulary_entries' in s and 'vocabulary_scope_plan' not in s for s in sql)
    monkeypatch.setattr(query,'_can_plan_location_scope',lambda **_:False)
    expected=func(**params)
    assert actual==expected



def test_unlimited_standard_scope_returns_every_group(database,monkeypatch):
    conn,session,sql=database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
        ((1,'同名',f'归一组{i:05}','日头','a') for i in range(5000)))
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
        ((1,'范围外','无关','无关','a') for _ in range(100000)))
    conn.commit();sql.clear()
    result=query.query_vocabulary_standard_words(session=session,**PARAMS,limit=None)
    assert planned(sql)
    assert any('CROSS JOIN vocabulary_entries' in s and 'vocabulary_scope_plan' not in s for s in sql)
    assert result.total==len(result.standard_words)==5001
    monkeypatch.setattr(query,'_can_plan_location_scope',lambda **_:False)
    assert result==query.query_vocabulary_standard_words(session=session,**PARAMS,limit=None)


@pytest.mark.parametrize('endpoint',['standard','map'])
def test_aggregate_planning_and_select_share_snapshot(database,endpoint):
    import sqlite3
    conn,session,sql=database
    conn.execute('PRAGMA journal_mode=WAL')
    wrote=False
    with sqlite3.connect(conn.execute('PRAGMA database_list').fetchone()[2]) as writer:
        def trace(statement):
            nonlocal wrote
            sql.append(statement)
            if 'CROSS JOIN vocabulary_entries' in statement and 'vocabulary_scope_plan' not in statement and not wrote:
                writer.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(1,'同名','新增词','日头','a')")
                writer.commit();wrote=True
        conn.set_trace_callback(trace)
        func=query.query_vocabulary_standard_words if endpoint=='standard' else query.query_vocabulary_map_points
        result=func(session=session,**PARAMS,**({'limit':None} if endpoint=='standard' else {}))
    assert wrote
    if endpoint=='standard':assert result.total==1 and result.standard_words[0].entry_count==2
    else:assert result.total_entries==2
    assert not conn.in_transaction


@pytest.mark.parametrize('endpoint',['standard','map'])
@pytest.mark.parametrize('fails',[False,True])
def test_aggregate_scope_preserves_callers_transaction(database,endpoint,fails):
    import sqlite3
    conn,session,_=database
    conn.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(1,'同名','太阳','日头','a')")
    func=query.query_vocabulary_standard_words if endpoint=='standard' else query.query_vocabulary_map_points
    try:
        if fails:
            conn.set_authorizer(lambda action,table,*_:sqlite3.SQLITE_DENY
                if action==sqlite3.SQLITE_READ and table=='vocabulary_locations' else sqlite3.SQLITE_OK)
            with pytest.raises(sqlite3.DatabaseError):func(session=session,**PARAMS)
        else:func(session=session,**PARAMS)
    finally:conn.set_authorizer(None)
    assert conn.in_transaction
    conn.rollback()
    assert conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0]==4


def test_scoped_map_returns_all_user_identities_without_point_limit(database,monkeypatch):
    conn,session,sql=database
    conn.executemany('INSERT INTO vocabulary_locations(user_id,location_name,coordinates) VALUES(?,?,?)',
        ((i+100,'同名','106,27') for i in range(700)))
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
        ((i+100,'同名','共同','共同','a') for i in range(700)))
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
        ((1,'范围外','无关','无关','a') for _ in range(10000)))
    conn.commit();sql.clear()
    params=dict(session=session,q='共同',search_fields=['headword'],locations=['同名'])
    actual=query.query_vocabulary_map_points(**params)
    assert planned(sql)
    assert any('CROSS JOIN vocabulary_entries' in s and 'vocabulary_scope_plan' not in s for s in sql)
    assert actual.total_entries==actual.total_points==len(actual.points)==700
    monkeypatch.setattr(query,'_can_plan_location_scope',lambda **_:False)
    assert actual==query.query_vocabulary_map_points(**params)
