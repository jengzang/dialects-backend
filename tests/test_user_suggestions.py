from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.routes.admin import suggestions as admin_suggestion_routes
from app.routes.user import suggestions as user_suggestion_routes
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


def _make_user_client(db_session, current_user):
    app = FastAPI()
    app.include_router(user_suggestion_routes.router, prefix="/api")

    def override_db():
        yield db_session

    async def override_current_user():
        return current_user

    app.dependency_overrides[user_suggestion_routes.get_db_custom] = override_db
    app.dependency_overrides[user_suggestion_routes.get_current_user] = override_current_user
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


def test_invalid_category_is_rejected_by_schema(db_session):
    client = _make_user_client(db_session, current_user=None)

    response = client.post(
        "/api/suggestions",
        json={
            "title": "bad category",
            "content": "bad category",
            "category": "not-a-category",
        },
    )

    assert response.status_code == 422
    assert db_session.query(UserSuggestion).count() == 0


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


def test_admin_list_filters_by_status_and_category(db_session):
    db_session.add_all(
        [
            UserSuggestion(title="open feature", content="a", category="feature"),
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


def test_admin_update_sets_handler_fields_for_terminal_status(db_session):
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
    assert body["handled_by"] == 1
    assert body["handled_by_username"] == "admin"
    assert body["handled_at"] is not None


def test_migration_creates_user_suggestions_table_idempotently(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration-test.db'}")

    migrate_user_suggestions_table(bind=engine)
    migrate_user_suggestions_table(bind=engine)

    inspector = inspect(engine)
    assert "user_suggestions" in inspector.get_table_names()
    index_names = {
        item["name"] for item in inspector.get_indexes("user_suggestions")
    }
    assert "idx_user_suggestions_user_id" in index_names
    assert "idx_user_suggestions_status" in index_names
    assert "idx_user_suggestions_category" in index_names
    assert "idx_user_suggestions_created_at" in index_names
    engine.dispose()
