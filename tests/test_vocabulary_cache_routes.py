"""HTTP cache integration against temporary SQLite and real isolated Redis."""
import asyncio
from contextlib import contextmanager
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_vocabulary_cache import cache


def test_cancelled_upload_drains_commit_and_invalidates_before_session_cleanup(monkeypatch):
    import io
    import threading
    from starlette.datastructures import UploadFile
    from app.routes import vocabulary
    entered = threading.Event()
    release = threading.Event()
    events = []
    def import_upload(**kwargs):
        entered.set()
        release.wait(5)
        events.append('commit')
        return {'ok': True}
    monkeypatch.setattr(vocabulary, 'import_vocabulary_upload', import_upload)
    monkeypatch.setattr(vocabulary, 'notify_vocabulary_change', lambda *args, **kwargs: events.append('invalidate'))
    db = SimpleNamespace(get_bind=lambda: SimpleNamespace(url=SimpleNamespace(database='test.db')))
    async def scenario():
        task = asyncio.create_task(vocabulary.upload_vocabulary(
            file=UploadFile(io.BytesIO(b'test'), filename='test.xlsx'), location='{}',
            parser_mode='auto', overwrite=False, fill_standard_from_local=False,
            target_user_id=None, current_user=None, db=db))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            task.cancel()
            await asyncio.sleep(.02)
            assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert events == ['commit', 'invalidate']
        finally:
            release.set()
    asyncio.run(scenario())


@pytest.fixture
def api(cache, monkeypatch):
    cache.max_keys = 128
    cache.max_bytes = 128 * 1024
    from app.routes import vocabulary, vocabulary_sql
    from app.service.vocabulary import cache as module
    from app.service.vocabulary.cache_warmup import warm_once
    from app.service.vocabulary.database import create_vocabulary_engine_and_session, get_db
    from app.service.vocabulary.models import Base, VocabularyEntry, VocabularyLocation
    from app.service.auth.core.dependencies import get_current_user
    from app.service.logging.dependencies import ApiLimiter
    from app.sql import sql_admin_routes, sql_routes

    engine, factory = create_vocabulary_engine_and_session(cache.db_path)
    Base.metadata.create_all(engine)
    with factory() as session:
        session.add(VocabularyLocation(user_id=1, location_name="甲", coordinates="106,27"))
        session.add(VocabularyEntry(user_id=1, location_name="甲", standard_word="太阳", local_expression="日头", ipa="a"))
        session.commit()
    monkeypatch.setattr(module, "get_vocabulary_cache", lambda path: cache)
    monkeypatch.setattr(vocabulary, "_resolve_usernames", lambda ids: {})
    monkeypatch.setitem(sql_routes.DB_MAPPING, "vocabulary", cache.db_path)
    @contextmanager
    def connection(*args, **kwargs):
        conn = sqlite3.connect(cache.db_path)
        try:
            yield conn
        finally:
            conn.close()
    monkeypatch.setattr(sql_admin_routes, "get_db_connection", connection)
    app = FastAPI()
    app.include_router(vocabulary.router, prefix="/vocabulary")
    app.include_router(vocabulary_sql.router, prefix="/vocabulary/sql")
    app.include_router(sql_admin_routes.router, prefix="/sql")
    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = db
    user = SimpleNamespace(id=1, role="admin", username="admin")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[ApiLimiter] = lambda: user
    app.dependency_overrides[sql_admin_routes.get_auth_db] = lambda: None
    asyncio.run(warm_once(cache, factory, pause=0))
    yield TestClient(app), factory
    engine.dispose()


def test_search_uses_prewarmed_result_without_querying(cache, api, monkeypatch):
    from app.routes import vocabulary
    client, _ = api
    def unexpected(**kwargs):
        pytest.fail("prewarmed query executed SQLite again")
    monkeypatch.setattr(vocabulary, "query_vocabulary_items", unexpected)
    response = client.get("/vocabulary/search/entries")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert client.get("/vocabulary/search/entries?search_fields=invalid").status_code == 400


@pytest.mark.parametrize("path,payload", [
    ("/vocabulary/sql/mutate", {"action": "update", "pk_value": 1, "data": {"ipa": "b"}}),
    ("/vocabulary/sql/batch-mutate", {"action": "batch_update", "update_data": [{"id": 1, "ipa": "b"}]}),
    ("/vocabulary/sql/batch-replace-execute", {"columns": ["ipa"], "find_text": "a", "replace_text": "b", "match_mode": "exact"}),
    ("/sql/mutate", {"db_key": "vocabulary", "table_name": "vocabulary_entries", "action": "update", "pk_value": 1, "data": {"ipa": "b"}}),
    ("/sql/batch-mutate", {"db_key": "vocabulary", "table_name": "vocabulary_entries", "action": "batch_update", "update_data": [{"id": 1, "ipa": "b"}]}),
    ("/sql/batch-replace-execute", {"db_key": "vocabulary", "table_name": "vocabulary_entries", "columns": ["ipa"], "find_text": "a", "replace_text": "b", "match_mode": "exact"}),
])
def test_entry_writes_invalidate_all_and_can_rewarm(cache, api, path, payload):
    from app.service.vocabulary.cache_warmup import warm_once
    client, factory = api
    old = cache.key("entries", {})
    payload = {**payload, "pk_column": "id"} if "mutate" in path else {**payload, "is_empty_search": False}
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.text
    assert cache.key("entries", {}) != old
    asyncio.run(warm_once(cache, factory, pause=0))
    assert client.get("/vocabulary/search/entries").json()["items"][0]["ipa"] == "b"
    # Cleanup is paged over the shared keyspace; obsolete keys may remain
    # physically present until later pages, but can never be the current value.
    assert cache.read(cache.key('entries', {}))['items'][0]['ipa'] == 'b'


@pytest.mark.parametrize("method,path,payload,entry_change", [
    ("patch", "/vocabulary/locations/甲", {"coordinates": "107,28"}, False),
    ("patch", "/vocabulary/locations/甲", {"new_location_name": "乙"}, True),
    ("delete", "/vocabulary/locations/甲", None, True),
    ("post", "/sql/mutate", {"db_key": "vocabulary", "table_name": "vocabulary_locations", "action": "update", "pk_value": 1, "data": {"coordinates": "107,28"}}, False),
])
def test_location_write_scopes(cache, api, method, path, payload, entry_change):
    client, _ = api
    old_entries = cache.key("entries", {})
    entry_revision = cache.state()['entries']
    old_map = cache.key("map-points", {})
    response = client.request(method, path, json=payload)
    assert response.status_code == 200, response.text
    assert (cache.state()['entries'] != entry_revision) is entry_change
    assert cache.key("entries", {}) != old_entries
    assert cache.key("map-points", {}) != old_map


@pytest.mark.parametrize("path,payload", [
    ("/vocabulary/sql/mutate", {"action": "update", "pk_value": 1, "data": {"ipa": "a"}}),
    ("/vocabulary/sql/batch-mutate", {"action": "batch_update", "update_data": [{"id": 1, "ipa": "a"}]}),
    ("/vocabulary/sql/batch-replace-execute", {"columns": ["ipa"], "find_text": "a", "replace_text": "a", "match_mode": "exact"}),
    ("/sql/mutate", {"db_key": "vocabulary", "table_name": "vocabulary_entries", "action": "update", "pk_value": 1, "data": {"ipa": "a"}}),
])
def test_noop_does_not_invalidate(cache, api, path, payload):
    client, _ = api
    old = cache.key("entries", {})
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.text
    assert cache.key("entries", {}) == old


def test_failed_write_keeps_cached_version(cache, api):
    client, _ = api
    old = cache.key("entries", {})
    response = client.post("/vocabulary/sql/mutate", json={"action": "update", "pk_value": 999, "data": {"ipa": "b"}})
    assert response.status_code == 404
    assert cache.key("entries", {}) == old


def test_upload_invalidates_and_rewarms_counts(cache, api):
    import io
    import json
    from openpyxl import Workbook
    from app.service.vocabulary.cache_warmup import warm_once
    client, factory = api
    book = Workbook()
    book.active.append(["标准词", "方言词", "音标"])
    book.active.append(["月亮", "月光", "b"])
    stream = io.BytesIO()
    book.save(stream)
    old = cache.key("entries", {})
    response = client.post("/vocabulary/imports", files={"file": ("words.xlsx", stream.getvalue())},
        data={"location": json.dumps({"location_name": "乙", "coordinates": "107,28"})})
    assert response.status_code == 200, response.text
    assert cache.key("entries", {}) != old
    asyncio.run(warm_once(cache, factory, pause=0))
    assert cache.read(cache.key("sql-count", {})) == {"count": 2}
    assert cache.read(cache.key("sql-count", {"distinct_column": "location_name"})) == {"count": 2}


def test_transfer_invalidates_entries_and_map(cache, api, monkeypatch):
    from app.routes import vocabulary
    client, _ = api
    monkeypatch.setattr(vocabulary, "_resolve_user_reference", lambda user_id, username, role_label: (user_id, str(user_id)))
    old_entries = cache.key("entries", {})
    old_map = cache.key("map-points", {})
    response = client.post("/vocabulary/locations/transfer", json={"location_name": "甲", "user_id": 1, "target_user_id": 2})
    assert response.status_code == 200, response.text
    assert cache.key("entries", {}) != old_entries
    assert cache.key("map-points", {}) != old_map


@pytest.mark.parametrize("path,payload", [
    ("/vocabulary/sql/query", {"page_size": 20}),
    ("/vocabulary/sql/distinct-query", {"target_column": "ipa"}),
])
def test_sql_repeated_queries_hit_cache(cache, api, monkeypatch, path, payload):
    from app.routes import vocabulary_sql
    client, _ = api
    first = client.post(path, json=payload)
    assert first.status_code == 200
    target = "_query_table_sync" if path.endswith("/query") else "_get_distinct_query_values_sync"
    monkeypatch.setattr(vocabulary_sql, target, lambda *args: pytest.fail("SQL result not cached"))
    assert client.post(path, json=payload).json() == first.json()


def test_count_uses_permanent_prewarm_and_checks_invalid_columns(cache, api, monkeypatch):
    from app.routes import vocabulary_sql
    client, _ = api
    monkeypatch.setattr(vocabulary_sql, "_get_table_count_sync", lambda *args, **kwargs: pytest.fail("default count not cached"))
    response = client.get("/vocabulary/sql/query/count?distinct_column=location_name")
    assert response.json() == {"count": 1}
    assert client.get("/vocabulary/sql/query/count?distinct_column=invalid").status_code == 400


def test_partial_batch_commit_invalidates_and_no_matches_does_not(cache, api):
    client, _ = api
    old = cache.key("entries", {})
    response = client.post("/vocabulary/sql/batch-mutate", json={"action": "batch_update", "update_data": [{"id": 1, "ipa": "b"}, {"id": 999, "ipa": "c"}]})
    assert response.status_code == 200
    assert response.json()["success_count"] == 1
    assert response.json()["error_count"] == 1
    assert cache.key("entries", {}) != old
    current = cache.key("entries", {})
    response = client.post("/vocabulary/sql/batch-replace-execute", json={"columns": ["ipa"], "find_text": "absent", "replace_text": "c"})
    assert response.status_code == 200
    assert response.json()["affected_rows"] == 0
    assert cache.key("entries", {}) == current


def test_exact_search_count_reused_across_pages_and_invalidated(cache, api):
    from app.service.vocabulary.models import VocabularyEntry
    client, factory = api
    with factory() as session:
        session.add_all([VocabularyEntry(user_id=1, location_name='甲', standard_word='共享计数', local_expression='a', ipa='a') for _ in range(7)])
        session.commit()
    cache.invalidate('entries')
    statements = []
    with factory() as session:
        session.connection().connection.set_trace_callback(statements.append)
    try:
        for page in (1, 2, 3, 4):
            response = client.get('/vocabulary/search/entries', params={'q': '共享计数', 'page': page, 'page_size': 2})
            assert response.status_code == 200, response.text
            assert response.json()['total'] == 7
            assert len(response.json()['items']) == (1 if page == 4 else 2)
        counts = [sql for sql in statements if sql.startswith('SELECT COUNT(*) FROM vocabulary_entries e')]
        assert len(counts) == 1
        with factory() as session:
            session.add(VocabularyEntry(user_id=1, location_name='甲', standard_word='共享计数', local_expression='b', ipa='b'))
            session.commit()
        cache.invalidate('entries')
        response = client.get('/vocabulary/search/entries', params={'q': '共享计数', 'page': 4, 'page_size': 2})
        assert response.json()['total'] == 8
        assert len(response.json()['items']) == 2
    finally:
        with factory() as session:
            session.connection().connection.set_trace_callback(None)


def test_count_location_filter_tracks_location_revision(cache, api):
    from app.service.vocabulary.models import VocabularyLocation
    client, factory = api
    params = {'province': '贵州', 'page_size': 1}
    assert client.get('/vocabulary/search/entries', params=params).json()['total'] == 0
    with factory() as session:
        session.query(VocabularyLocation).update({'province': '贵州'})
        session.commit()
    cache.invalidate('locations')
    result = client.get('/vocabulary/search/entries', params=params).json()
    assert result['total'] == len(result['items']) == 1


def test_inferred_first_page_count_is_reused_and_invalidated(cache, api):
    from app.service.vocabulary.models import VocabularyEntry
    client, factory = api
    params = {'q': '日头', 'locations': '甲', 'search_fields': 'headword'}
    statements = []
    with factory() as session:
        session.connection().connection.set_trace_callback(statements.append)
    try:
        first = client.get('/vocabulary/search/entries', params=params)
        assert first.status_code == 200, first.text
        assert first.json()['total'] == len(first.json()['items']) == 1
        for page in (1, 2):
            response = client.get('/vocabulary/search/entries', params={**params, 'page': page, 'page_size': 1})
            assert response.status_code == 200, response.text
            assert response.json()['total'] == 1
            assert len(response.json()['items']) == (1 if page == 1 else 0)
        assert not any(sql.startswith('SELECT COUNT(*)') for sql in statements)
        with factory() as session:
            session.add(VocabularyEntry(user_id=1, location_name='甲', standard_word='太阳', local_expression='日头', ipa='b'))
            session.commit()
        cache.invalidate('entries')
        response = client.get('/vocabulary/search/entries', params={**params, 'page': 2, 'page_size': 1})
        assert response.json()['total'] == 2
        assert len(response.json()['items']) == 1
        assert any(sql.startswith('SELECT COUNT(*)') for sql in statements)
    finally:
        with factory() as session:
            session.connection().connection.set_trace_callback(None)


def test_scoped_first_page_count_hit_skips_planner_with_real_redis(cache,api,monkeypatch):
    from app.service.vocabulary import query
    client,_=api
    original=query.plan_location_scope
    planned=[]
    def observe(*args,**kwargs):
        planned.append(kwargs['locations'])
        return original(*args,**kwargs)
    monkeypatch.setattr(query,'plan_location_scope',observe)
    params={'q':'日头','search_fields':'headword','locations':'甲','page_size':1}
    first=client.get('/vocabulary/search/entries',params=params)
    assert first.status_code==200
    assert first.json()['total']==len(first.json()['items'])==1
    assert len(planned)==1
    # Different page size misses the response cache, reuses the exact count key.
    second=client.get('/vocabulary/search/entries',params=dict(params,page_size=2))
    assert second.status_code==200
    assert second.json()['total']==1
    assert second.json()['items']==first.json()['items']
    assert len(planned)==1
