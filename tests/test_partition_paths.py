import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.routes.geo.get_partitions import router
from app.service.auth.core.dependencies import get_current_user
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations, query_dialect_abbreviations_orm
from app.service.user.core.database import get_db
from app.service.user.core.models import Base, Information
from app.sql.db_selector import get_query_db


@pytest.fixture
def databases(tmp_path):
    path = tmp_path / "query.db"
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE dialects (音典分區 TEXT, 地圖集二分區 TEXT, 簡稱 TEXT, 存儲標記 TEXT)')
        connection.executemany('INSERT INTO dialects VALUES (?, ?, ?, ?)', [
            ("甲-桂林", "粵語-四邑片", "直接", "1"),
            ("甲-桂林-小區", "粵語-四邑片-小片", "後代", "1"),
            ("乙-桂林", "吳語-四邑片", "另一分支", "1"),
            ("甲-桂林外", "粵語-四邑片外", "邊界外", "1"),
            ("甲-桂林-未存", "粵語-未存", "未存", ""),
            ("甲-百分%-底_\\-子", "粵語-其他", "特殊字", "1"),
            ("甲-百分X-底A\\-子", "粵語-其他", "通配誤選", "1"),
            ("待处理-隱藏", None, "隱藏", "1"),
        ])
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for index, (partition, abbr, owner) in enumerate([
            ("甲-桂林", "用戶直接", 1), ("甲-桂林-子", "用戶後代", 1),
            ("乙-桂林", "用戶同名", 1), ("私人-額外", "用戶額外", 1),
            ("他人-秘密", "他人", 2), ("甲-桂林-他人", "他人後代", 2),
        ]):
            session.add(Information(簡稱=abbr, 音典分區=partition, 經緯度="0,0", 特徵="測試", 值="值",
                                    maxValue="值", user_id=owner, username=str(owner), 存儲標記=1))
        session.commit()
        yield str(path), session
    engine.dispose()


def test_sql_parent_includes_direct_and_descendants_with_deduplication(databases):
    result = query_dialect_abbreviations(["甲-桂林", "甲-桂林-小區"], ["直接", "明選"], db_path=databases[0])
    assert result == ["直接", "後代", "明選"]
    assert query_dialect_abbreviations(["甲-桂林"], db_path=databases[0]) == ["直接", "後代"]
    assert query_dialect_abbreviations(["桂林"], db_path=databases[0]) == []
    assert query_dialect_abbreviations(["甲-桂林-不存在"], db_path=databases[0]) == []


def test_sql_modes_storage_and_literal_wildcards(databases):
    assert query_dialect_abbreviations(["粵語-四邑片"], db_path=databases[0], region_mode="map") == ["直接", "後代"]
    assert query_dialect_abbreviations(["甲-桂林"], db_path=databases[0], need_storage_flag=False) == ["直接", "後代", "未存"]
    assert query_dialect_abbreviations(["甲-百分%-底_\\"], db_path=databases[0]) == ["特殊字"]
    assert query_dialect_abbreviations([], ["明選", "明選"], db_path=databases[0]) == ["明選"]


def test_orm_uses_same_path_boundaries_and_current_user(databases):
    result = query_dialect_abbreviations_orm(databases[1], SimpleNamespace(id=1), ["甲-桂林", "甲-桂林-子"], ["用戶直接", "明選"])
    assert result == ["用戶直接", "用戶後代", "明選"]
    assert query_dialect_abbreviations_orm(databases[1], SimpleNamespace(id=1), ["桂林"], []) == []
    assert query_dialect_abbreviations_orm(databases[1], SimpleNamespace(id=1), ["他人"], []) == []


@pytest.fixture
def resolve_client(databases):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_query_db] = lambda: databases[0]
    app.dependency_overrides[get_db] = lambda: databases[1]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    return app


@pytest.mark.anyio
async def test_resolve_names_paths_sources_and_user_isolation(resolve_client):
    from httpx import ASGITransport, AsyncClient
    async with AsyncClient(transport=ASGITransport(app=resolve_client), base_url="http://test") as client:
        response = await client.post("/api/partitions/resolve", json={"region_mode": "yindian", "scope": "default_and_user", "items": [
            {"text": "桂林", "kind": "name"}, {"text": "甲-桂林", "kind": "path"},
            {"text": "額外", "kind": "name"}, {"text": "秘密", "kind": "name"},
            {"text": "小区", "kind": "name"}, {"text": "待处理-隱藏", "kind": "path"},
        ]})
        assert response.status_code == 200
        items = response.json()["items"]
        assert items[0]["status"] == "ambiguous"
        assert {c["path"] for c in items[0]["candidates"]} == {"甲-桂林", "乙-桂林"}
        assert items[1]["status"] == "resolved"
        assert set(items[1]["candidates"][0]["sources"]) == {"default", "user"}
        assert items[2]["candidates"][0]["path"] == "私人-額外"
        assert items[3]["status"] == "not_found"
        assert items[4]["candidates"][0]["path"] == "甲-桂林-小區"
        assert items[5]["status"] == "resolved"
        map_response = await client.post("/api/partitions/resolve", json={"region_mode": "map", "scope": "default_and_user", "items": [{"text": "額外", "kind": "name"}]})
        assert map_response.json()["items"][0]["status"] == "not_found"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_paths_preserve_ascii_case_identity(databases):
    with sqlite3.connect(databases[0]) as connection:
        connection.executemany('INSERT INTO dialects VALUES (?, ?, ?, ?)', [
            ("甲-A-子", None, "大寫", "1"), ("甲-a-子", None, "小寫", "1")])
    assert query_dialect_abbreviations(["甲-A"], db_path=databases[0]) == ["大寫"]
    for path, abbr in [("甲-A-子", "大寫"), ("甲-a-子", "小寫")]:
        databases[1].add(Information(簡稱=abbr, 音典分區=path, 經緯度="0,0", 特徵="測試", 值="值",
                                    maxValue="值", user_id=1, username="1", 存儲標記=1))
    databases[1].commit()
    assert query_dialect_abbreviations_orm(databases[1], SimpleNamespace(id=1), ["甲-A"], []) == ["大寫"]


@pytest.mark.anyio
async def test_resolve_scope_authentication_and_validation(resolve_client):
    from httpx import ASGITransport, AsyncClient
    async with AsyncClient(transport=ASGITransport(app=resolve_client), base_url="http://test") as client:
        payload = {"region_mode": "yindian", "scope": "default", "items": [{"text": "額外", "kind": "name"}]}
        assert (await client.post("/api/partitions/resolve", json=payload)).json()["items"][0]["status"] == "not_found"
        resolve_client.dependency_overrides[get_current_user] = lambda: None
        payload["scope"] = "default_and_user"
        assert (await client.post("/api/partitions/resolve", json=payload)).json()["items"][0]["status"] == "not_found"
        for invalid in [{"text": "甲--乙", "kind": "path"}, {"text": "甲", "kind": "other"}, {"text": " 甲", "kind": "path"}]:
            payload["items"] = [invalid]
            assert (await client.post("/api/partitions/resolve", json=payload)).status_code == 422
