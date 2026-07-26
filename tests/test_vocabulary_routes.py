from inspect import signature
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routes.vocabulary import (
    get_my_vocabulary_context,
    get_vocabulary_items,
    get_vocabulary_location_options,
    get_vocabulary_logs,
    get_vocabulary_locations,
    get_vocabulary_map_points,
    get_vocabulary_permission,
    get_vocabulary_permissions,
    preview_vocabulary_upload_endpoint,
    update_vocabulary_location,
    upload_vocabulary,
)
from app.service.auth.core.dependencies import get_current_admin_user, get_current_user
from app.service.vocabulary.database import create_vocabulary_engine_and_session
from app.service.vocabulary.models import Base, VocabularyLocation, VocabularyLog, VocabularyPermission


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


def test_upload_preview_endpoint_depends_on_current_user() -> None:
    dependency = signature(preview_vocabulary_upload_endpoint).parameters["current_user"].default.dependency
    assert dependency is get_current_user


def test_my_permission_endpoint_depends_on_current_user() -> None:
    dependency = signature(get_my_vocabulary_context).parameters["current_user"].default.dependency
    assert dependency is get_current_user


def test_main_routes_registers_vocabulary_import_endpoints_and_legacy_upload_aliases() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/imports" in paths
    assert "/api/vocabulary/imports/preview" in paths
    assert "/api/vocabulary/upload" in paths
    assert "/api/vocabulary/upload/preview" in paths


def test_main_routes_registers_my_vocabulary_context_endpoint_and_legacy_permission_alias() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/me" in paths
    assert "/api/vocabulary/me/permission" in paths


def test_main_routes_registers_vocabulary_search_entries_endpoint_and_legacy_items_alias() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/search/entries" in paths
    assert "/api/vocabulary/items" in paths


def test_items_endpoint_accepts_query_parameters() -> None:
    parameters = signature(get_vocabulary_items).parameters

    assert "q" in parameters
    assert "search_fields" in parameters
    assert "locations" in parameters
    assert "page" in parameters
    assert "page_size" in parameters


def test_main_routes_registers_vocabulary_search_map_points_endpoint_and_legacy_alias() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/search/map-points" in paths
    assert "/api/vocabulary/map-points" in paths


def test_map_points_endpoint_accepts_filter_parameters_without_pagination() -> None:
    parameters = signature(get_vocabulary_map_points).parameters

    assert "q" in parameters
    assert "search_fields" in parameters
    assert "locations" in parameters
    assert "page" not in parameters
    assert "page_size" not in parameters


def test_main_routes_registers_vocabulary_search_location_options_endpoint_and_legacy_alias() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/search/location-options" in paths
    assert "/api/vocabulary/location-options" in paths


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
