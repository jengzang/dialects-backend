from inspect import signature
from pathlib import Path

from app.routes.vocabulary import get_vocabulary_items, upload_vocabulary
from app.service.auth.core.dependencies import get_current_admin_user, get_current_user
from app.service.vocabulary.database import create_vocabulary_engine_and_session
from app.service.vocabulary.models import Base, VocabularyLog, VocabularyPermission


class _User:
    def __init__(self, user_id: int, role: str = "user"):
        self.id = user_id
        self.role = role


def _make_session(tmp_path: Path):
    engine, session_factory = create_vocabulary_engine_and_session(tmp_path / "vocabulary.db")
    Base.metadata.create_all(bind=engine)
    return session_factory()


def test_upload_endpoint_depends_on_current_user() -> None:
    dependency = signature(upload_vocabulary).parameters["current_user"].default.dependency
    assert dependency is get_current_user


def test_main_routes_registers_vocabulary_upload_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/upload" in paths


def test_main_routes_registers_vocabulary_items_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/items" in paths


def test_items_endpoint_accepts_query_parameters() -> None:
    parameters = signature(get_vocabulary_items).parameters

    assert "q" in parameters
    assert "search_fields" in parameters
    assert "locations" in parameters
    assert "page" in parameters
    assert "page_size" in parameters


def test_main_routes_registers_vocabulary_sql_endpoints() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/sql/query" in paths
    assert "/api/vocabulary/sql/mutate" in paths
    assert "/api/vocabulary/sql/batch-replace-execute" in paths


def test_admin_permission_endpoint_depends_on_admin_user() -> None:
    from app.routes.vocabulary import set_vocabulary_permission

    dependency = signature(set_vocabulary_permission).parameters["current_admin"].default.dependency
    assert dependency is get_current_admin_user


def test_main_routes_registers_vocabulary_permission_admin_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/admin/permissions/{user_id}" in paths


def test_admin_permission_endpoint_upserts_vocabulary_permission(tmp_path: Path) -> None:
    from app.routes.vocabulary import set_vocabulary_permission
    from app.schemas.vocabulary import VocabularyPermissionUpdateRequest

    session = _make_session(tmp_path)
    try:
        created = set_vocabulary_permission(
            user_id=7,
            params=VocabularyPermissionUpdateRequest(permission_level="edit"),
            current_admin=_User(1, role="admin"),
            db=session,
        )
        updated = set_vocabulary_permission(
            user_id=7,
            params=VocabularyPermissionUpdateRequest(permission_level="manage"),
            current_admin=_User(1, role="admin"),
            db=session,
        )

        row = session.query(VocabularyPermission).filter(VocabularyPermission.user_id == 7).one()
        assert created.user_id == 7
        assert created.permission_level == "edit"
        assert updated.user_id == 7
        assert updated.permission_level == "manage"
        assert row.permission_level == "manage"
    finally:
        session.close()


def test_admin_permission_endpoint_writes_vocabulary_log(tmp_path: Path) -> None:
    from app.routes.vocabulary import set_vocabulary_permission
    from app.schemas.vocabulary import VocabularyPermissionUpdateRequest

    session = _make_session(tmp_path)
    try:
        set_vocabulary_permission(
            user_id=7,
            params=VocabularyPermissionUpdateRequest(permission_level="edit"),
            current_admin=_User(1, role="admin"),
            db=session,
        )

        log = session.query(VocabularyLog).one()
        assert log.user_id == 1
        assert log.permission_level == "manage"
        assert log.source == "admin"
        assert log.action == "set_permission"
        assert log.table_name == "vocabulary_permissions"
        assert log.affected_rows == 1
        assert "target_user_id = 7" in log.target_scope
    finally:
        session.close()
