from inspect import signature
import json
from sqlite3 import OperationalError as SqliteOperationalError
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.routes.vocabulary import (
    get_my_vocabulary_context,
    get_vocabulary_items,
    get_vocabulary_location_options,
    get_vocabulary_logs,
    get_vocabulary_locations,
    get_vocabulary_map_items,
    get_vocabulary_map_points,
    get_vocabulary_permission,
    get_vocabulary_permissions,
    get_vocabulary_standard_words,
    preview_vocabulary_upload_endpoint,
    update_vocabulary_location,
    upload_vocabulary,
)
from app.service.auth.core.dependencies import get_current_admin_user, get_current_user
from app.service.vocabulary.database import create_vocabulary_engine_and_session
from app.service.vocabulary.models import Base, VocabularyEntry, VocabularyLocation, VocabularyLog, VocabularyPermission


class _User:
    def __init__(self, user_id: int, role: str = "user", username: str | None = None):
        self.id = user_id
        self.role = role
        self.username = username or f"user_{user_id}"


class _FakeAuthQuery:
    def __init__(self, users):
        self.users = users
        self.field = None
        self.value = None

    def filter(self, criterion):
        self.field = criterion.left.key
        self.value = criterion.right.value
        return self

    def first(self):
        for user in self.users:
            if getattr(user, self.field) == self.value:
                return user
        return None

    def all(self):
        match = self.first()
        return [match] if match is not None else []


class _FakeAuthSession:
    def __init__(self, users):
        self.users = users

    def query(self, *args):
        return _FakeAuthQuery(self.users)

    def close(self):
        pass


def _patch_auth_users(monkeypatch, users):
    from app.routes import vocabulary as vocabulary_routes

    monkeypatch.setattr(
        vocabulary_routes,
        "AuthSessionLocal",
        lambda: _FakeAuthSession(users),
    )


def _make_session(tmp_path: Path):
    engine, session_factory = create_vocabulary_engine_and_session(tmp_path / "vocabulary.db")
    Base.metadata.create_all(bind=engine)
    return session_factory()


def test_upload_endpoint_depends_on_current_user() -> None:
    dependency = signature(upload_vocabulary).parameters["current_user"].default.dependency
    assert dependency is get_current_user


def test_upload_preview_endpoint_depends_on_current_user() -> None:
    dependency = signature(preview_vocabulary_upload_endpoint).parameters["current_user"].default.dependency
    assert dependency is get_current_user


def test_my_permission_endpoint_depends_on_current_user() -> None:
    dependency = signature(get_my_vocabulary_context).parameters["current_user"].default.dependency
    assert dependency is get_current_user


def test_main_routes_registers_only_vocabulary_import_endpoints() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/imports" in paths
    assert "/api/vocabulary/imports/preview" in paths
    assert "/api/vocabulary/upload" not in paths
    assert "/api/vocabulary/upload/preview" not in paths


def test_main_routes_registers_only_my_vocabulary_context_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/me" in paths
    assert "/api/vocabulary/me/permission" not in paths


def test_main_routes_registers_vocabulary_location_transfer_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/locations/transfer" in paths


def test_my_vocabulary_context_endpoint_rejects_anonymous_request() -> None:
    from app.main import app

    response = TestClient(app).get("/api/vocabulary/me")

    assert response.status_code == 401


def test_vocabulary_api_config_requires_login_for_private_routes() -> None:
    from app.service.logging.utils.route_matcher import match_route_config

    paths = [
        "/api/vocabulary/me",
        "/api/vocabulary/imports",
        "/api/vocabulary/imports/preview",
        "/api/vocabulary/locations",
        "/api/vocabulary/locations/transfer",
        "/api/vocabulary/locations/息烽",
        "/api/vocabulary/logs",
    ]

    for path in paths:
        config = match_route_config(path)
        assert config["rate_limit"] is True
        assert config["require_login"] is True


def test_vocabulary_sql_api_config_matches_public_sql_entry_policy() -> None:
    from app.service.logging.utils.route_matcher import match_route_config

    paths = [
        "/api/vocabulary/sql/query",
        "/api/vocabulary/sql/query/columns",
        "/api/vocabulary/sql/distinct/vocabulary_entries/standard_word",
        "/api/vocabulary/sql/distinct-query",
        "/api/vocabulary/sql/mutate",
        "/api/vocabulary/sql/batch-mutate",
        "/api/vocabulary/sql/batch-replace-preview",
        "/api/vocabulary/sql/batch-replace-execute",
    ]

    for path in paths:
        config = match_route_config(path)
        assert config["rate_limit"] is True
        assert config["require_login"] is False

    count_config = match_route_config("/api/vocabulary/sql/query/count")
    assert count_config["rate_limit"] is False
    assert count_config["require_login"] is False


def test_vocabulary_search_api_config_is_public_but_rate_limited() -> None:
    from app.service.logging.utils.route_matcher import match_route_config

    paths = [
        "/api/vocabulary/search/entries",
        "/api/vocabulary/search/map-points",
        "/api/vocabulary/search/map-items",
        "/api/vocabulary/search/location-options",
        "/api/vocabulary/search/standard-words",
    ]

    for path in paths:
        config = match_route_config(path)
        assert config["rate_limit"] is True
        assert config["require_login"] is False


def test_vocabulary_admin_api_config_skips_limiter_for_admin_dependency() -> None:
    from app.service.logging.utils.route_matcher import match_route_config

    config = match_route_config("/api/vocabulary/admin/permissions/7")

    assert config["is_whitelisted"] is True
    assert config["rate_limit"] is False
    assert config["require_login"] is False


def test_main_routes_registers_only_vocabulary_search_entries_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/search/entries" in paths
    assert "/api/vocabulary/items" not in paths


def test_items_endpoint_accepts_query_parameters() -> None:
    parameters = signature(get_vocabulary_items).parameters

    assert "q" in parameters
    assert "search_fields" in parameters
    assert "locations" in parameters
    assert "standard_words" in parameters
    assert "page" in parameters
    assert "page_size" in parameters


def test_main_routes_registers_only_vocabulary_search_map_points_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/search/map-points" in paths
    assert "/api/vocabulary/map-points" not in paths


def test_map_points_endpoint_accepts_filter_parameters_without_pagination() -> None:
    parameters = signature(get_vocabulary_map_points).parameters

    assert "q" in parameters
    assert "search_fields" in parameters
    assert "locations" in parameters
    assert "page" not in parameters
    assert "page_size" not in parameters


def test_main_routes_registers_vocabulary_search_standard_words_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/search/standard-words" in paths


def test_standard_words_endpoint_accepts_optional_filters_without_required_query() -> None:
    parameters = signature(get_vocabulary_standard_words).parameters

    assert "q" in parameters
    assert "search_fields" in parameters
    assert "locations" in parameters
    assert "limit" in parameters
    assert parameters["q"].default.default is None
    assert parameters["limit"].default.default == 100


def test_main_routes_registers_vocabulary_search_map_items_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/search/map-items" in paths


def test_map_items_endpoint_accepts_standard_word_filters_without_pagination() -> None:
    parameters = signature(get_vocabulary_map_items).parameters

    assert "standard_words" in parameters
    assert "q" in parameters
    assert "search_fields" in parameters
    assert "locations" in parameters
    assert "page" not in parameters
    assert "page_size" not in parameters


def test_main_routes_registers_only_vocabulary_search_location_options_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/search/location-options" in paths
    assert "/api/vocabulary/location-options" not in paths


def test_location_options_endpoint_is_public_read_shape() -> None:
    parameters = signature(get_vocabulary_location_options).parameters

    assert "db" in parameters
    assert "current_user" not in parameters
    assert "user_id" not in parameters
    assert "page" not in parameters
    assert "page_size" not in parameters


def test_main_routes_registers_vocabulary_locations_endpoints() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/locations" in paths
    assert "/api/vocabulary/locations/{location_name}" in paths


def test_locations_endpoints_depend_on_current_user() -> None:
    for endpoint in (get_vocabulary_locations, update_vocabulary_location):
        dependency = signature(endpoint).parameters["current_user"].default.dependency
        assert dependency is get_current_user


def test_logs_endpoint_depends_on_current_user() -> None:
    dependency = signature(get_vocabulary_logs).parameters["current_user"].default.dependency
    assert dependency is get_current_user


def test_main_routes_registers_vocabulary_logs_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/logs" in paths


def test_location_update_schema_rejects_location_name() -> None:
    from app.schemas.vocabulary import VocabularyLocationUpdateRequest

    assert "location_name" not in VocabularyLocationUpdateRequest.model_fields
    with pytest.raises(ValidationError):
        VocabularyLocationUpdateRequest(location_name="新简称", city="贵阳")


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

    for endpoint in (
        get_vocabulary_permission,
        get_vocabulary_permissions,
        set_vocabulary_permission,
    ):
        dependency = signature(endpoint).parameters["current_admin"].default.dependency
        assert dependency is get_current_admin_user


def test_main_routes_registers_vocabulary_permission_admin_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/admin/permissions" in paths
    assert "/api/vocabulary/admin/permissions/{user_id}" in paths


def test_admin_permissions_endpoint_lists_vocabulary_permissions(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyPermission(user_id=9, permission_level="manage"),
                VocabularyPermission(user_id=7, permission_level="edit"),
            ]
        )
        session.commit()

        result = get_vocabulary_permissions(
            page=1,
            page_size=50,
            current_admin=_User(1, role="admin"),
            db=session,
        )

        assert result.total == 2
        assert result.page == 1
        assert result.page_size == 50
        assert [(row.user_id, row.permission_level) for row in result.permissions] == [
            (7, "edit"),
            (9, "manage"),
        ]
    finally:
        session.close()


def test_admin_permission_endpoint_gets_user_permission_or_null(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.commit()

        existing = get_vocabulary_permission(
            user_id=7,
            current_admin=_User(1, role="admin"),
            db=session,
        )
        missing = get_vocabulary_permission(
            user_id=8,
            current_admin=_User(1, role="admin"),
            db=session,
        )

        assert existing.user_id == 7
        assert existing.permission_level == "edit"
        assert missing.user_id == 8
        assert missing.permission_level is None
    finally:
        session.close()


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


def test_admin_permission_endpoint_logs_permission_revocation(tmp_path: Path) -> None:
    from app.routes.vocabulary import set_vocabulary_permission
    from app.schemas.vocabulary import VocabularyPermissionUpdateRequest

    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.commit()

        result = set_vocabulary_permission(
            user_id=7,
            params=VocabularyPermissionUpdateRequest(permission_level="none"),
            current_admin=_User(1, role="admin"),
            db=session,
        )

        log = session.query(VocabularyLog).one()
        payload = json.loads(log.payload_json)
        assert result.user_id == 7
        assert result.permission_level is None
        assert session.query(VocabularyPermission).filter(VocabularyPermission.user_id == 7).count() == 0
        assert log.user_id == 1
        assert log.source == "admin"
        assert log.action == "set_permission"
        assert log.table_name == "vocabulary_permissions"
        assert log.affected_rows == 1
        assert payload["before"] == {"permission_level": "edit"}
        assert payload["after"] is None
        assert payload["rollback_supported"] is True
    finally:
        session.close()


def test_admin_permission_log_records_previous_permission(tmp_path: Path) -> None:
    from app.routes.vocabulary import set_vocabulary_permission
    from app.schemas.vocabulary import VocabularyPermissionUpdateRequest

    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.commit()

        set_vocabulary_permission(
            user_id=7,
            params=VocabularyPermissionUpdateRequest(permission_level="manage"),
            current_admin=_User(1, role="admin"),
            db=session,
        )

        payload = json.loads(session.query(VocabularyLog).one().payload_json)
        assert payload["before"] == {"permission_level": "edit"}
        assert payload["after"] == {"permission_level": "manage"}
        assert payload["rollback_supported"] is True
    finally:
        session.close()


def test_admin_permission_endpoint_translates_locked_database_to_503(tmp_path: Path, monkeypatch) -> None:
    from app.routes import vocabulary as vocabulary_routes
    from app.routes.vocabulary import set_vocabulary_permission
    from app.schemas.vocabulary import VocabularyPermissionUpdateRequest

    session = _make_session(tmp_path)

    def raise_locked(*args, **kwargs):
        raise SqliteOperationalError("database is locked")

    monkeypatch.setattr(vocabulary_routes, "record_vocabulary_log", raise_locked)
    try:
        with pytest.raises(HTTPException) as raised:
            set_vocabulary_permission(
                user_id=7,
                params=VocabularyPermissionUpdateRequest(permission_level="edit"),
                current_admin=_User(1, role="admin"),
                db=session,
            )

        assert raised.value.status_code == 503
        assert "正在写入" in raised.value.detail
    finally:
        session.close()


def test_my_permission_endpoint_returns_effective_permission_or_null(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.commit()

        edit_result = get_my_vocabulary_context(
            current_user=_User(7),
            db=session,
        )
        missing_result = get_my_vocabulary_context(
            current_user=_User(8),
            db=session,
        )
        admin_result = get_my_vocabulary_context(
            current_user=_User(1, role="admin"),
            db=session,
        )

        assert edit_result.user_id == 7
        assert edit_result.permission_level == "edit"
        assert edit_result.can_upload is True
        assert edit_result.can_manage_entries is False
        assert edit_result.can_view_logs is False
        assert missing_result.user_id == 8
        assert missing_result.permission_level is None
        assert missing_result.can_upload is False
        assert missing_result.can_manage_entries is False
        assert missing_result.can_view_logs is False
        assert admin_result.user_id == 1
        assert admin_result.permission_level == "manage"
        assert admin_result.can_upload is True
        assert admin_result.can_manage_entries is True
        assert admin_result.can_view_logs is True
    finally:
        session.close()


def test_upload_preview_endpoint_returns_counts_without_writing_database(tmp_path: Path) -> None:
    class _UploadFile:
        filename = "upload.csv"

        async def read(self):
            return (
                "written,vocabulary,ipa,notes\n"
                "太阳,日头,ȵit2 tʰəu2,常用\n"
            ).encode("utf-8")

    import asyncio

    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.commit()

        result = asyncio.run(
            preview_vocabulary_upload_endpoint(
                file=_UploadFile(),
                location='{"location_name":"息烽","coordinates":"106.73,27.10"}',
                parser_mode="table",
                current_user=_User(7),
                db=session,
            )
        )

        assert result.success is True
        assert result.location_name == "息烽"
        assert result.parsed_count == 1
        assert result.would_delete_existing_count == 0
        assert session.query(VocabularyLocation).count() == 0
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_upload_endpoint_returns_409_when_current_user_location_exists_without_overwrite(tmp_path: Path) -> None:
    class _UploadFile:
        filename = "upload.csv"

        async def read(self):
            return (
                "written,vocabulary,ipa,notes\n"
                "太阳,日头,ȵit2 tʰəu2,常用\n"
            ).encode("utf-8")

    import asyncio

    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.add(
            VocabularyEntry(
                user_id=7,
                location_name="息烽",
                standard_word="旧词",
                local_expression="旧讲法",
                ipa="old1",
            )
        )
        session.commit()

        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                upload_vocabulary(
                    file=_UploadFile(),
                    location='{"location_name":"息烽","coordinates":"106.73,27.10"}',
                    parser_mode="table",
                    overwrite=False,
                    current_user=_User(7),
                    db=session,
                )
            )

        assert raised.value.status_code == 409
        assert "已有数据" in raised.value.detail
    finally:
        session.close()


def test_edit_locations_list_only_returns_current_users_rows(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.73,27.10",
                    province="贵州",
                ),
                VocabularyLocation(
                    user_id=8,
                    location_name="罗田胜利",
                    coordinates="115.46,31.13",
                    province="湖北",
                ),
            ]
        )
        session.commit()

        result = get_vocabulary_locations(
            user_id=None,
            username=None,
            location_name=None,
            page=1,
            page_size=20,
            current_user=_User(7),
            db=session,
        )

        assert result.total == 1
        assert [row.user_id for row in result.locations] == [7]
        assert result.locations[0].location_name == "息烽"
    finally:
        session.close()


def test_manage_locations_list_can_filter_by_user_id_and_location_name(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.73,27.10",
                    province="贵州",
                ),
                VocabularyLocation(
                    user_id=8,
                    location_name="息烽",
                    coordinates="106.74,27.11",
                    province="贵州",
                ),
                VocabularyLocation(
                    user_id=8,
                    location_name="罗田胜利",
                    coordinates="115.46,31.13",
                    province="湖北",
                ),
            ]
        )
        session.commit()

        result = get_vocabulary_locations(
            user_id=8,
            username=None,
            location_name="息烽",
            page=1,
            page_size=20,
            current_user=_User(1, role="admin"),
            db=session,
        )

        assert result.total == 1
        assert result.locations[0].user_id == 8
        assert result.locations[0].location_name == "息烽"
    finally:
        session.close()


def test_edit_location_patch_updates_own_location_and_logs(tmp_path: Path) -> None:
    from app.schemas.vocabulary import VocabularyLocationUpdateRequest

    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="old",
                    province="贵州",
                ),
                VocabularyLocation(
                    user_id=8,
                    location_name="息烽",
                    coordinates="other",
                    province="贵州",
                ),
            ]
        )
        session.commit()

        result = update_vocabulary_location(
            location_name="息烽",
            params=VocabularyLocationUpdateRequest(
                coordinates="106.734862,27.09809",
                city="贵阳",
                county="息烽",
            ),
            user_id=None,
            current_user=_User(7),
            db=session,
        )

        own = session.query(VocabularyLocation).filter(
            VocabularyLocation.user_id == 7,
            VocabularyLocation.location_name == "息烽",
        ).one()
        other = session.query(VocabularyLocation).filter(
            VocabularyLocation.user_id == 8,
            VocabularyLocation.location_name == "息烽",
        ).one()
        log = session.query(VocabularyLog).one()

        assert result.user_id == 7
        assert result.location_name == "息烽"
        assert own.coordinates == "106.734862,27.09809"
        assert own.city == "贵阳"
        assert other.coordinates == "other"
        assert log.user_id == 7
        assert log.permission_level == "edit"
        assert log.source == "location_editor"
        assert log.action == "update_location"
        assert log.table_name == "vocabulary_locations"
        assert log.affected_rows == 1
        assert "user_id = 7" in log.target_scope
        assert "location_name = 息烽" in log.target_scope
    finally:
        session.close()


def test_edit_location_patch_cannot_target_other_user_id(tmp_path: Path) -> None:
    from app.schemas.vocabulary import VocabularyLocationUpdateRequest

    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.add(
            VocabularyLocation(
                user_id=8,
                location_name="息烽",
                coordinates="other",
            )
        )
        session.commit()

        with pytest.raises(HTTPException) as raised:
            update_vocabulary_location(
                location_name="息烽",
                params=VocabularyLocationUpdateRequest(city="贵阳"),
                user_id=8,
                current_user=_User(7),
                db=session,
            )

        assert raised.value.status_code == 403
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_manage_location_patch_requires_user_id_when_name_is_ambiguous(tmp_path: Path) -> None:
    from app.schemas.vocabulary import VocabularyLocationUpdateRequest

    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.73,27.10",
                ),
                VocabularyLocation(
                    user_id=8,
                    location_name="息烽",
                    coordinates="106.74,27.11",
                ),
            ]
        )
        session.commit()

        with pytest.raises(HTTPException) as raised:
            update_vocabulary_location(
                location_name="息烽",
                params=VocabularyLocationUpdateRequest(city="贵阳"),
                user_id=None,
                current_user=_User(1, role="admin"),
                db=session,
            )

        assert raised.value.status_code == 400
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_manage_location_patch_can_update_target_user_location(tmp_path: Path) -> None:
    from app.schemas.vocabulary import VocabularyLocationUpdateRequest

    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.73,27.10",
                    city="旧",
                ),
                VocabularyLocation(
                    user_id=8,
                    location_name="息烽",
                    coordinates="106.74,27.11",
                    city="旧",
                ),
            ]
        )
        session.commit()

        result = update_vocabulary_location(
            location_name="息烽",
            params=VocabularyLocationUpdateRequest(city="贵阳"),
            user_id=8,
            current_user=_User(1, role="admin"),
            db=session,
        )

        target = session.query(VocabularyLocation).filter(
            VocabularyLocation.user_id == 8,
            VocabularyLocation.location_name == "息烽",
        ).one()
        untouched = session.query(VocabularyLocation).filter(
            VocabularyLocation.user_id == 7,
            VocabularyLocation.location_name == "息烽",
        ).one()
        log = session.query(VocabularyLog).one()

        assert result.user_id == 8
        assert target.city == "贵阳"
        assert untouched.city == "旧"
        assert log.user_id == 1
        assert log.permission_level == "manage"
        assert "user_id = 8" in log.target_scope
    finally:
        session.close()


def test_manage_user_can_transfer_location_and_entries_by_user_id(tmp_path: Path, monkeypatch) -> None:
    from app.routes import vocabulary as vocabulary_routes

    _patch_auth_users(
        monkeypatch,
        [
            SimpleNamespace(id=7, username="alice"),
            SimpleNamespace(id=8, username="bob"),
        ],
    )
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.73,27.10",
                    city="贵阳",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="ȵit2",
                ),
                VocabularyPermission(user_id=9, permission_level="manage"),
            ]
        )
        session.commit()

        result = vocabulary_routes.transfer_vocabulary_location(
            params=SimpleNamespace(
                location_name="息烽",
                user_id=7,
                username=None,
                target_user_id=8,
                target_username=None,
            ),
            current_user=_User(9),
            db=session,
        )

        transferred_location = session.query(VocabularyLocation).filter(
            VocabularyLocation.user_id == 8,
            VocabularyLocation.location_name == "息烽",
        ).one()
        transferred_entry = session.query(VocabularyEntry).filter(
            VocabularyEntry.user_id == 8,
            VocabularyEntry.location_name == "息烽",
        ).one()
        log = session.query(VocabularyLog).one()
        payload = json.loads(log.payload_json)

        assert result.success is True
        assert result.source_user_id == 7
        assert result.source_username == "alice"
        assert result.target_user_id == 8
        assert result.target_username == "bob"
        assert result.transferred_entries_count == 1
        assert transferred_location.city == "贵阳"
        assert transferred_entry.standard_word == "太阳"
        assert log.action == "transfer_location"
        assert log.table_name == "vocabulary_locations"
        assert log.affected_rows == 2
        assert payload["source_user_id"] == 7
        assert payload["source_username"] == "alice"
        assert payload["target_user_id"] == 8
        assert payload["target_username"] == "bob"
        assert payload["transferred_entries_count"] == 1
        assert payload["rollback_supported"] is True
    finally:
        session.close()


def test_manage_user_can_transfer_location_by_usernames(tmp_path: Path, monkeypatch) -> None:
    from app.routes import vocabulary as vocabulary_routes

    _patch_auth_users(
        monkeypatch,
        [
            SimpleNamespace(id=7, username="alice"),
            SimpleNamespace(id=8, username="bob"),
        ],
    )
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.73,27.10",
                ),
                VocabularyPermission(user_id=9, permission_level="manage"),
            ]
        )
        session.commit()

        result = vocabulary_routes.transfer_vocabulary_location(
            params=SimpleNamespace(
                location_name="息烽",
                user_id=None,
                username="alice",
                target_user_id=None,
                target_username="bob",
            ),
            current_user=_User(9),
            db=session,
        )

        assert result.source_user_id == 7
        assert result.target_user_id == 8
        assert session.query(VocabularyLocation).filter(
            VocabularyLocation.user_id == 8,
            VocabularyLocation.location_name == "息烽",
        ).count() == 1
    finally:
        session.close()


def test_transfer_location_endpoint_accepts_http_request(tmp_path: Path, monkeypatch) -> None:
    from app.main import app
    from app.service.vocabulary.database import get_db as get_vocabulary_db

    _patch_auth_users(
        monkeypatch,
        [
            SimpleNamespace(id=7, username="alice"),
            SimpleNamespace(id=8, username="bob"),
        ],
    )
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.73,27.10",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="ȵit2",
                ),
                VocabularyPermission(user_id=9, permission_level="manage"),
            ]
        )
        session.commit()

        previous_overrides = dict(app.dependency_overrides)
        app.dependency_overrides[get_current_user] = lambda: _User(9)
        app.dependency_overrides[get_vocabulary_db] = lambda: session
        try:
            response = TestClient(app).post(
                "/api/vocabulary/locations/transfer",
                json={
                    "location_name": "息烽",
                    "username": "alice",
                    "target_username": "bob",
                },
            )
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "location_name": "息烽",
            "permission_level": "manage",
            "source_user_id": 7,
            "source_username": "alice",
            "target_user_id": 8,
            "target_username": "bob",
            "transferred_entries_count": 1,
        }
        assert session.query(VocabularyLocation).filter(
            VocabularyLocation.user_id == 8,
            VocabularyLocation.location_name == "息烽",
        ).count() == 1
        assert session.query(VocabularyEntry).filter(
            VocabularyEntry.user_id == 8,
            VocabularyEntry.location_name == "息烽",
        ).count() == 1
    finally:
        session.close()


def test_manage_user_cannot_transfer_to_existing_same_name_location(tmp_path: Path, monkeypatch) -> None:
    from app.routes import vocabulary as vocabulary_routes

    _patch_auth_users(
        monkeypatch,
        [
            SimpleNamespace(id=7, username="alice"),
            SimpleNamespace(id=8, username="bob"),
        ],
    )
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.73,27.10",
                ),
                VocabularyLocation(
                    user_id=8,
                    location_name="息烽",
                    coordinates="106.74,27.11",
                ),
                VocabularyPermission(user_id=9, permission_level="manage"),
            ]
        )
        session.commit()

        with pytest.raises(HTTPException) as raised:
            vocabulary_routes.transfer_vocabulary_location(
                params=SimpleNamespace(
                    location_name="息烽",
                    user_id=7,
                    username=None,
                    target_user_id=8,
                    target_username=None,
                ),
                current_user=_User(9),
                db=session,
            )

        assert raised.value.status_code == 409
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_edit_user_cannot_transfer_location(tmp_path: Path, monkeypatch) -> None:
    from app.routes import vocabulary as vocabulary_routes

    _patch_auth_users(
        monkeypatch,
        [
            SimpleNamespace(id=7, username="alice"),
            SimpleNamespace(id=8, username="bob"),
        ],
    )
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyPermission(user_id=7, permission_level="edit"),
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.73,27.10",
                ),
            ]
        )
        session.commit()

        with pytest.raises(HTTPException) as raised:
            vocabulary_routes.transfer_vocabulary_location(
                params=SimpleNamespace(
                    location_name="息烽",
                    user_id=7,
                    username=None,
                    target_user_id=8,
                    target_username=None,
                ),
                current_user=_User(7),
                db=session,
            )

        assert raised.value.status_code == 403
        assert session.query(VocabularyLocation).filter(
            VocabularyLocation.user_id == 7,
            VocabularyLocation.location_name == "息烽",
        ).count() == 1
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_edit_user_cannot_read_vocabulary_logs_endpoint(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.commit()

        with pytest.raises(HTTPException) as raised:
            get_vocabulary_logs(
                user_id=None,
                permission_level=None,
                source=None,
                action=None,
                table_name=None,
                status=None,
                page=1,
                page_size=50,
                current_user=_User(7),
                db=session,
            )

        assert raised.value.status_code == 403
    finally:
        session.close()


def test_manage_user_can_read_vocabulary_logs_endpoint(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="manage"))
        session.add(
            VocabularyLog(
                operation_id="op-1",
                user_id=8,
                permission_level="edit",
                source="upload",
                action="import",
                table_name="vocabulary_entries",
                target_scope="user_id = 8",
                affected_rows=12,
                status="success",
                payload_json='{"location_name":"息烽"}',
            )
        )
        session.commit()

        result = get_vocabulary_logs(
            user_id=8,
            permission_level=None,
            source="upload",
            action=None,
            table_name=None,
            status=None,
            page=1,
            page_size=50,
            current_user=_User(7),
            db=session,
        )

        assert result.total == 1
        assert result.logs[0].operation_id == "op-1"
        assert result.logs[0].user_id == 8
        assert result.logs[0].source == "upload"
        assert result.logs[0].payload_json == '{"location_name":"息烽"}'
    finally:
        session.close()
