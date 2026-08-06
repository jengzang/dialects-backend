import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.routes.admin import suggestions as admin_suggestion_routes
from app.routes.user import suggestions as user_suggestion_routes
from app.service.auth.database.models import ApiUsageLog
from app.service.user.core.database import migrate_user_suggestions_table
from app.service.user.core.models import Base, UserSuggestion


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'supplements-test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def auth_db_session(tmp_path):
    from app.service.auth.database.models import Base as AuthBase

    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth-test.db'}",
        connect_args={"check_same_thread": False},
    )
    AuthBase.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_user_client(db_session, current_user, auth_db_session=None):
    app = FastAPI()
    app.include_router(user_suggestion_routes.router, prefix="/api")

    def override_db():
        yield db_session

    async def override_current_user():
        return current_user

    def override_auth_db():
        yield auth_db_session

    app.dependency_overrides[user_suggestion_routes.get_db_custom] = override_db
    app.dependency_overrides[user_suggestion_routes.get_current_user] = override_current_user
    app.dependency_overrides[user_suggestion_routes.get_auth_db] = override_auth_db
    return TestClient(app)


def _make_admin_client(db_session, current_admin):
    app = FastAPI()
    app.include_router(admin_suggestion_routes.router, prefix="/admin/suggestions")

    def override_db():
        yield db_session

    async def override_current_admin_user():
        return current_admin

    app.dependency_overrides[admin_suggestion_routes.get_db_custom] = override_db
    app.dependency_overrides[
        admin_suggestion_routes.get_current_admin_user
    ] = override_current_admin_user
    return TestClient(app)


def test_anonymous_submit_stores_no_user_identity(db_session):
    client = _make_user_client(db_session, current_user=None)

    response = client.post(
        "/api/suggestions",
        json={
            "title": "地图筛选希望保留上次选择",
            "content": "每次切换页面后筛选条件会重置，希望能记住。",
            "category": "feature",
            "source_path": "/map",
            "context": {"region": "嶺南-珠江"},
            "contact": "guest@example.com",
        },
        headers={"user-agent": "pytest-agent"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    row = db_session.query(UserSuggestion).one()
    assert row.user_id is None
    assert row.username is None
    assert row.category == "feature"
    assert row.status == "open"
    assert row.priority == "normal"
    assert row.context_json == '{"region": "嶺南-珠江"}'
    assert row.contact == "guest@example.com"
    assert row.user_agent == "pytest-agent"


def test_authenticated_submit_stores_user_identity(db_session):
    user = SimpleNamespace(id=7, username="tester")
    client = _make_user_client(db_session, current_user=user)

    response = client.post(
        "/api/suggestions",
        json={
            "title": "补一个数据问题入口",
            "content": "希望每条数据旁边可以直接反馈错误。",
            "category": "data_issue",
        },
    )

    assert response.status_code == 200
    row = db_session.query(UserSuggestion).one()
    assert row.user_id == 7
    assert row.username == "tester"


def test_custom_category_is_accepted(db_session):
    client = _make_user_client(db_session, current_user=None)

    response = client.post(
        "/api/suggestions",
        json={
            "title": "性能建议",
            "content": "地图接口可以加缓存。",
            "category": "performance_idea",
        },
    )

    assert response.status_code == 200
    row = db_session.query(UserSuggestion).one()
    assert row.category == "performance_idea"


def test_submit_accepts_supported_image_data_url_without_returning_it(db_session):
    client = _make_user_client(db_session, current_user=None)
    image_base64 = "data:image/webp;base64,d2VicC1ieXRlcw=="

    response = client.post(
        "/api/suggestions",
        json={
            "title": "截图反馈",
            "content": "按钮遮住了文字。",
            "image_base64": image_base64,
        },
    )

    assert response.status_code == 200
    assert "image_base64" not in response.json()
    row = db_session.query(UserSuggestion).one()
    assert row.image_base64 == image_base64


def test_submit_rejects_unsupported_image_data_url(db_session):
    client = _make_user_client(db_session, current_user=None)

    response = client.post(
        "/api/suggestions",
        json={
            "title": "错误图片",
            "content": "gif 不应被收。",
            "image_base64": "data:image/gif;base64,Z2lm",
        },
    )

    assert response.status_code == 422


def test_submit_rejects_image_over_size_limit(db_session):
    client = _make_user_client(db_session, current_user=None)
    oversized = "data:image/png;base64," + ("A" * (1024 * 1024 + 4))

    response = client.post(
        "/api/suggestions",
        json={
            "title": "太大的截图",
            "content": "这张图超过限制。",
            "image_base64": oversized,
        },
    )

    assert response.status_code == 422


def test_my_suggestions_requires_login(db_session):
    client = _make_user_client(db_session, current_user=None)

    response = client.get("/api/suggestions/my")

    assert response.status_code == 401


def test_my_suggestions_only_returns_current_user_rows(db_session):
    db_session.add_all(
        [
            UserSuggestion(
                user_id=7,
                username="tester",
                title="mine",
                content="my suggestion",
                category="feature",
                image_base64="data:image/png;base64,bWluZQ==",
            ),
            UserSuggestion(
                user_id=8,
                username="other",
                title="other",
                content="other suggestion",
                category="bug",
            ),
            UserSuggestion(
                title="anonymous",
                content="anonymous suggestion",
                category="general",
            ),
        ]
    )
    db_session.commit()
    client = _make_user_client(
        db_session,
        current_user=SimpleNamespace(id=7, username="tester"),
    )

    response = client.get("/api/suggestions/my")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["total"] == 1
    assert [item["title"] for item in body["items"]] == ["mine"]
    assert "image_base64" not in body["items"][0]


def test_admin_list_filters_by_status_and_category(db_session):
    db_session.add_all(
        [
            UserSuggestion(
                title="open feature",
                content="a",
                category="feature",
                image_base64="data:image/jpeg;base64,anBn",
            ),
            UserSuggestion(title="open bug", content="b", category="bug"),
            UserSuggestion(
                title="done feature",
                content="c",
                category="feature",
                status="done",
            ),
        ]
    )
    db_session.commit()
    client = _make_admin_client(
        db_session,
        current_admin=SimpleNamespace(id=1, username="admin", role="admin"),
    )

    response = client.get("/admin/suggestions?status=open&category=feature")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "open feature"
    assert body["items"][0]["image_base64"] == "data:image/jpeg;base64,anBn"


def test_submit_records_recent_api_from_user_id_then_ip(db_session, auth_db_session):
    now = datetime(2026, 8, 1, 12, 0, 0)
    auth_db_session.add_all(
        [
            ApiUsageLog(
                id=1,
                user_id=7,
                path="/api/user-old",
                duration=0.3,
                status_code=200,
                ip="10.0.0.1",
                called_at=now - timedelta(minutes=3),
            ),
            ApiUsageLog(
                id=2,
                user_id=7,
                path="/api/user-new",
                duration=0.1,
                status_code=500,
                ip="10.0.0.1",
                called_at=now - timedelta(minutes=1),
            ),
            ApiUsageLog(
                id=3,
                user_id=None,
                path="/api/ip-fill",
                duration=0.2,
                status_code=404,
                ip="10.0.0.1",
                called_at=now - timedelta(minutes=2),
            ),
            ApiUsageLog(
                id=4,
                user_id=99,
                path="/api/other-ip",
                duration=0.4,
                status_code=200,
                ip="10.0.0.2",
                called_at=now,
            ),
        ]
    )
    auth_db_session.commit()
    client = _make_user_client(
        db_session,
        current_user=SimpleNamespace(id=7, username="tester"),
        auth_db_session=auth_db_session,
    )

    response = client.post(
        "/api/suggestions",
        json={"title": "看上下文", "content": "请看最近请求"},
        headers={"x-forwarded-for": "10.0.0.1"},
    )

    assert response.status_code == 200
    row = db_session.query(UserSuggestion).one()
    recent_api = json.loads(row.recent_api)
    assert recent_api == [
        {"name": "/api/user-new", "time": "2026-08-01T11:59:00", "duration": 0.1},
        {"name": "/api/user-old", "time": "2026-08-01T11:57:00", "duration": 0.3},
        {"name": "/api/ip-fill", "time": "2026-08-01T11:58:00", "duration": 0.2},
    ]
    assert all("status_code" not in item for item in recent_api)


def test_anonymous_submit_records_recent_api_by_ip(db_session, auth_db_session):
    called_at = datetime(2026, 8, 1, 12, 0, 0)
    auth_db_session.add_all(
        [
            ApiUsageLog(
                user_id=None,
                path="/api/anonymous",
                duration=0.08,
                status_code=200,
                ip="10.0.0.3",
                called_at=called_at,
            ),
            ApiUsageLog(
                user_id=None,
                path="/api/different",
                duration=0.09,
                status_code=200,
                ip="10.0.0.4",
                called_at=called_at,
            ),
        ]
    )
    auth_db_session.commit()
    client = _make_user_client(
        db_session,
        current_user=None,
        auth_db_session=auth_db_session,
    )

    response = client.post(
        "/api/suggestions",
        json={"title": "匿名反馈", "content": "请看 IP 关联"},
        headers={"x-forwarded-for": "10.0.0.3"},
    )

    assert response.status_code == 200
    row = db_session.query(UserSuggestion).one()
    assert json.loads(row.recent_api) == [
        {"name": "/api/anonymous", "time": "2026-08-01T12:00:00", "duration": 0.08}
    ]


def test_admin_update_sets_handled_at_without_admin_identity_fields(db_session):
    suggestion = UserSuggestion(
        title="needs decision",
        content="please decide",
        category="feature",
    )
    db_session.add(suggestion)
    db_session.commit()
    client = _make_admin_client(
        db_session,
        current_admin=SimpleNamespace(id=1, username="admin", role="admin"),
    )

    response = client.patch(
        f"/admin/suggestions/{suggestion.id}",
        json={
            "status": "done",
            "priority": "high",
            "admin_note": "已处理",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["priority"] == "high"
    assert body["admin_note"] == "已处理"
    assert "handled_by" not in body
    assert "handled_by_username" not in body
    assert body["handled_at"] is not None


def test_migration_creates_user_suggestions_table_idempotently(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration-test.db'}")

    migrate_user_suggestions_table(bind=engine)
    migrate_user_suggestions_table(bind=engine)

    inspector = inspect(engine)
    assert "user_suggestions" in inspector.get_table_names()
    column_names = {
        item["name"] for item in inspector.get_columns("user_suggestions")
    }
    assert "recent_api" in column_names
    assert "image_base64" in column_names
    assert "handled_by" not in column_names
    assert "handled_by_username" not in column_names
    index_names = {
        item["name"] for item in inspector.get_indexes("user_suggestions")
    }
    assert "idx_user_suggestions_user_id" in index_names
    assert "idx_user_suggestions_status" in index_names
    assert "idx_user_suggestions_category" in index_names
    assert "idx_user_suggestions_created_at" in index_names
    engine.dispose()
