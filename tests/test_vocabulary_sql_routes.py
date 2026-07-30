import asyncio
import json
from inspect import signature
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.service.auth.core.dependencies import get_current_user
from app.service.vocabulary.database import create_vocabulary_engine_and_session
from app.service.vocabulary.models import (
    Base,
    VocabularyEntry,
    VocabularyLog,
    VocabularyPermission,
)


class _User:
    def __init__(self, user_id: int, role: str = "user"):
        self.id = user_id
        self.role = role


def _make_session(tmp_path: Path):
    engine, session_factory = create_vocabulary_engine_and_session(tmp_path / "vocabulary.db")
    Base.metadata.create_all(bind=engine)
    return session_factory()


def _grant_edit(session, user_id: int) -> None:
    session.add(VocabularyPermission(user_id=user_id, permission_level="edit"))
    session.commit()


def _seed_entries(session) -> tuple[int, int]:
    own = VocabularyEntry(
        user_id=7,
        location_name="息烽",
        standard_word="太阳",
        local_expression="日头",
        ipa="old",
        notes="own",
    )
    other = VocabularyEntry(
        user_id=8,
        location_name="息烽",
        standard_word="太阳",
        local_expression="太阳",
        ipa="old",
        notes="other",
    )
    session.add_all([own, other])
    session.commit()
    return own.id, other.id


def test_vocabulary_sql_endpoints_use_current_user_dependency() -> None:
    from app.routes.vocabulary_sql import (
        batch_mutate_table,
        batch_replace_execute,
        batch_replace_preview,
        get_column_info,
        get_distinct_path_values,
        get_distinct_query_values,
        get_table_count,
        mutate_table,
        query_table,
    )

    for endpoint in (
        query_table,
        get_column_info,
        get_table_count,
        get_distinct_path_values,
        get_distinct_query_values,
        mutate_table,
        batch_mutate_table,
        batch_replace_preview,
        batch_replace_execute,
    ):
        dependency = signature(endpoint).parameters["current_user"].default.dependency
        assert dependency is get_current_user


def test_vocabulary_sql_columns_endpoint_allows_anonymous_request() -> None:
    from app.main import app

    response = TestClient(app).get("/api/vocabulary/sql/query/columns")

    assert response.status_code == 200


def test_vocabulary_sql_schemas_do_not_accept_db_key() -> None:
    from app.schemas.vocabulary_sql import MutationParams, QueryParams

    assert "db_key" not in QueryParams.model_fields
    assert "db_key" not in MutationParams.model_fields


def test_vocabulary_sql_query_endpoint_allows_anonymous_request() -> None:
    from app.main import app

    response = TestClient(app).post(
        "/api/vocabulary/sql/query",
        json={"table_name": "vocabulary_entries", "page": 1, "page_size": 20},
    )

    assert response.status_code == 200


def test_logged_in_user_without_vocabulary_permission_can_query_public_entries(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import query_table
    from app.schemas.vocabulary_sql import QueryParams

    session = _make_session(tmp_path)
    try:
        _seed_entries(session)

        result = asyncio.run(
            query_table(
                QueryParams(
                    table_name="vocabulary_entries",
                    page=1,
                    page_size=20,
                ),
                current_user=_User(7),
                db=session,
            )
        )

        assert result["total"] == 2
        assert sorted(row["user_id"] for row in result["data"]) == [7, 8]
    finally:
        session.close()


def test_anonymous_mutate_still_requires_vocabulary_write_permission(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                mutate_table(
                    MutationParams(
                        table_name="vocabulary_entries",
                        action="create",
                        data={
                            "location_name": "息烽",
                            "standard_word": "太阳",
                            "local_expression": "日头",
                            "ipa": "ipa",
                        },
                    ),
                    current_user=None,
                    db=session,
                )
            )

        assert raised.value.status_code == 401
        assert session.query(VocabularyEntry).count() == 0
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_edit_query_can_read_all_public_entries(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import query_table
    from app.schemas.vocabulary_sql import QueryParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)
        _seed_entries(session)

        result = asyncio.run(
            query_table(
                QueryParams(
                    table_name="vocabulary_entries",
                    page=1,
                    page_size=20,
                ),
                current_user=_User(7),
                db=session,
            ),
        )

        assert result["total"] == 2
        assert sorted(row["user_id"] for row in result["data"]) == [7, 8]
    finally:
        session.close()


def test_edit_update_cannot_touch_other_users_entry_and_logs_attempt(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)
        _, other_id = _seed_entries(session)

        result = asyncio.run(
            mutate_table(
                MutationParams(
                    table_name="vocabulary_entries",
                    action="update",
                    pk_column="id",
                    pk_value=other_id,
                    data={"ipa": "new"},
                ),
                current_user=_User(7),
                db=session,
            ),
        )

        other = session.get(VocabularyEntry, other_id)
        log = session.query(VocabularyLog).one()

        assert result["affected_rows"] == 0
        assert other.ipa == "old"
        assert log.user_id == 7
        assert log.permission_level == "edit"
        assert log.operation_id
        assert log.source == "sql_editor"
        assert log.action == "update"
        assert log.status == "success"
        assert log.table_name == "vocabulary_entries"
        assert log.affected_rows == 0
        assert "user_id = 7" in log.target_scope
    finally:
        session.close()


def test_edit_batch_replace_is_user_scoped_and_logged(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import batch_replace_execute, batch_replace_preview
    from app.schemas.vocabulary_sql import BatchReplaceExecuteParams, BatchReplacePreviewParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)
        own_id, other_id = _seed_entries(session)

        preview = asyncio.run(
            batch_replace_preview(
                BatchReplacePreviewParams(
                    table_name="vocabulary_entries",
                    columns=["local_expression"],
                    find_text="日",
                    match_mode="contains",
                    is_empty_search=False,
                ),
                current_user=_User(7),
                db=session,
            ),
        )
        result = asyncio.run(
            batch_replace_execute(
                BatchReplaceExecuteParams(
                    table_name="vocabulary_entries",
                    columns=["local_expression"],
                    find_text="日",
                    replace_text="太陽",
                    match_mode="contains",
                    is_empty_search=False,
                ),
                current_user=_User(7),
                db=session,
            ),
        )

        own = session.get(VocabularyEntry, own_id)
        other = session.get(VocabularyEntry, other_id)
        log = session.query(VocabularyLog).one()

        assert preview["total_matches"] == 1
        assert result["affected_rows"] == 1
        assert own.local_expression == "太陽头"
        assert other.local_expression == "太阳"
        assert log.operation_id
        assert log.source == "batch_replace"
        assert log.action == "replace"
        assert log.status == "success"
        assert log.affected_rows == 1
        assert "user_id = 7" in log.target_scope
        payload = json.loads(log.payload_json)
        assert payload["filters"] == {}
        assert payload["search_text"] == ""
        assert payload["search_columns"] == []
        assert payload["rollback_supported"] is False
    finally:
        session.close()


def test_manage_batch_replace_can_touch_all_entries(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import batch_replace_execute
    from app.schemas.vocabulary_sql import BatchReplaceExecuteParams

    session = _make_session(tmp_path)
    try:
        own_id, other_id = _seed_entries(session)

        result = asyncio.run(
            batch_replace_execute(
                BatchReplaceExecuteParams(
                    table_name="vocabulary_entries",
                    columns=["ipa"],
                    find_text="old",
                    replace_text="new",
                    match_mode="exact",
                    is_empty_search=False,
                ),
                current_user=_User(1, role="admin"),
                db=session,
            ),
        )

        assert result["affected_rows"] == 2
        assert session.get(VocabularyEntry, own_id).ipa == "new"
        assert session.get(VocabularyEntry, other_id).ipa == "new"
    finally:
        session.close()


def test_vocabulary_sql_cannot_query_logs_table(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import query_table
    from app.schemas.vocabulary_sql import QueryParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)

        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                query_table(
                    QueryParams(table_name="vocabulary_logs"),
                    current_user=_User(7),
                    db=session,
                )
            )

        assert raised.value.status_code == 400
    finally:
        session.close()


def test_edit_create_forces_current_user_id(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)

        result = asyncio.run(
            mutate_table(
                MutationParams(
                    table_name="vocabulary_entries",
                    action="create",
                    data={
                        "user_id": 999,
                        "location_name": "息烽",
                        "standard_word": "月亮",
                        "local_expression": "月光",
                        "ipa": "ŋye",
                    },
                ),
                current_user=_User(7),
                db=session,
            )
        )

        row = session.query(VocabularyEntry).one()
        payload = json.loads(session.query(VocabularyLog).one().payload_json)
        assert result["affected_rows"] == 1
        assert row.user_id == 7
        assert payload["after"] == {"id": row.id}
        assert payload["rollback_supported"] is True
    finally:
        session.close()


def test_manage_create_also_uses_current_user_id(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        asyncio.run(
            mutate_table(
                MutationParams(
                    table_name="vocabulary_entries",
                    action="create",
                    data={
                        "user_id": 999,
                        "location_name": "息烽",
                        "standard_word": "风",
                        "local_expression": "风",
                        "ipa": "fuŋ",
                    },
                ),
                current_user=_User(1, role="admin"),
                db=session,
            )
        )

        row = session.query(VocabularyEntry).one()
        assert row.user_id == 1
    finally:
        session.close()


def test_update_rejects_user_id_changes(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)
        own_id, _ = _seed_entries(session)

        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                mutate_table(
                    MutationParams(
                        table_name="vocabulary_entries",
                        action="update",
                        pk_column="id",
                        pk_value=own_id,
                        data={"user_id": 8},
                    ),
                    current_user=_User(7),
                    db=session,
                )
            )

        assert raised.value.status_code == 400
        assert session.get(VocabularyEntry, own_id).user_id == 7
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_update_rejects_location_name_changes(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)
        own_id, _ = _seed_entries(session)

        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                mutate_table(
                    MutationParams(
                        table_name="vocabulary_entries",
                        action="update",
                        pk_column="id",
                        pk_value=own_id,
                        data={"location_name": "新地点"},
                    ),
                    current_user=_User(7),
                    db=session,
                )
            )

        assert raised.value.status_code == 400
        assert session.get(VocabularyEntry, own_id).location_name == "息烽"
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_update_log_records_previous_values_for_changed_columns(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)
        own_id, _ = _seed_entries(session)

        asyncio.run(
            mutate_table(
                MutationParams(
                    table_name="vocabulary_entries",
                    action="update",
                    pk_column="id",
                    pk_value=own_id,
                    data={"ipa": "new", "notes": "changed"},
                ),
                current_user=_User(7),
                db=session,
            )
        )

        payload = json.loads(session.query(VocabularyLog).one().payload_json)
        assert payload["before"] == {
            "id": own_id,
            "ipa": "old",
            "notes": "own",
        }
        assert payload["rollback_supported"] is True
    finally:
        session.close()


def test_edit_user_can_delete_own_single_entry_and_log_it(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)
        own_id, _ = _seed_entries(session)

        result = asyncio.run(
            mutate_table(
                MutationParams(
                    table_name="vocabulary_entries",
                    action="delete",
                    pk_column="id",
                    pk_value=own_id,
                ),
                current_user=_User(7),
                db=session,
            )
        )
        log = session.query(VocabularyLog).one()
        payload = json.loads(log.payload_json)

        assert result == {"status": "success", "action": "delete", "affected_rows": 1}
        assert session.get(VocabularyEntry, own_id) is None
        assert log.user_id == 7
        assert log.permission_level == "edit"
        assert log.action == "delete"
        assert log.affected_rows == 1
        assert payload["before"]["id"] == own_id
        assert payload["before"]["user_id"] == 7
        assert payload["before"]["standard_word"] == "太阳"
        assert payload["rollback_supported"] is True
    finally:
        session.close()


def test_edit_user_cannot_delete_other_users_entry(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)
        _, other_id = _seed_entries(session)

        result = asyncio.run(
            mutate_table(
                MutationParams(
                    table_name="vocabulary_entries",
                    action="delete",
                    pk_column="id",
                    pk_value=other_id,
                ),
                current_user=_User(7),
                db=session,
            )
        )
        log = session.query(VocabularyLog).one()
        payload = json.loads(log.payload_json)

        assert result == {"status": "success", "action": "delete", "affected_rows": 0}
        assert session.get(VocabularyEntry, other_id) is not None
        assert log.user_id == 7
        assert log.permission_level == "edit"
        assert log.action == "delete"
        assert log.affected_rows == 0
        assert payload["before"] is None
        assert payload["rollback_supported"] is False
    finally:
        session.close()


def test_manage_delete_log_records_deleted_row_snapshot(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        own_id, _ = _seed_entries(session)

        asyncio.run(
            mutate_table(
                MutationParams(
                    table_name="vocabulary_entries",
                    action="delete",
                    pk_column="id",
                    pk_value=own_id,
                ),
                current_user=_User(1, role="admin"),
                db=session,
            )
        )

        payload = json.loads(session.query(VocabularyLog).one().payload_json)
        assert payload["before"]["id"] == own_id
        assert payload["before"]["user_id"] == 7
        assert payload["before"]["standard_word"] == "太阳"
        assert payload["rollback_supported"] is True
    finally:
        session.close()


def test_manage_delete_log_records_rowid_when_used_as_pk(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        own_id, _ = _seed_entries(session)

        asyncio.run(
            mutate_table(
                MutationParams(
                    table_name="vocabulary_entries",
                    action="delete",
                    pk_column="rowid",
                    pk_value=own_id,
                ),
                current_user=_User(1, role="admin"),
                db=session,
            )
        )

        payload = json.loads(session.query(VocabularyLog).one().payload_json)
        assert payload["before"]["rowid"] == own_id
        assert payload["rollback_supported"] is True
    finally:
        session.close()


def test_edit_user_cannot_batch_delete_entries_through_vocabulary_sql(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import batch_mutate_table
    from app.schemas.vocabulary_sql import BatchMutationParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)
        own_id, _ = _seed_entries(session)

        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                batch_mutate_table(
                    BatchMutationParams(
                        table_name="vocabulary_entries",
                        action="batch_delete",
                        delete_ids=[own_id],
                    ),
                    current_user=_User(7),
                    db=session,
                )
            )

        assert raised.value.status_code == 403
        assert session.get(VocabularyEntry, own_id) is not None
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_batch_replace_rejects_location_name_column(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import batch_replace_execute
    from app.schemas.vocabulary_sql import BatchReplaceExecuteParams

    session = _make_session(tmp_path)
    try:
        _grant_edit(session, 7)
        _seed_entries(session)

        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                batch_replace_execute(
                    BatchReplaceExecuteParams(
                        table_name="vocabulary_entries",
                        columns=["location_name"],
                        find_text="息烽",
                        replace_text="新地点",
                    ),
                    current_user=_User(7),
                    db=session,
                )
            )

        assert raised.value.status_code == 400
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_vocabulary_sql_only_allows_entries_table(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import query_table
    from app.schemas.vocabulary_sql import QueryParams

    session = _make_session(tmp_path)
    try:
        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                query_table(
                    QueryParams(table_name="vocabulary_locations"),
                    current_user=_User(1, role="admin"),
                    db=session,
                )
            )

        assert raised.value.status_code == 400
    finally:
        session.close()


def test_manage_can_query_logs_through_dedicated_endpoint(tmp_path: Path) -> None:
    from app.routes.vocabulary import get_vocabulary_logs
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        asyncio.run(
            mutate_table(
                MutationParams(
                    table_name="vocabulary_entries",
                    action="create",
                    data={
                        "location_name": "息烽",
                        "standard_word": "水",
                        "local_expression": "水",
                        "ipa": "sui",
                    },
                ),
                current_user=_User(1, role="admin"),
                db=session,
            )
        )

        result = get_vocabulary_logs(
            user_id=None,
            permission_level=None,
            source=None,
            action=None,
            table_name=None,
            status=None,
            page=1,
            page_size=50,
            current_user=_User(1, role="admin"),
            db=session,
        )

        assert result.total == 1
        assert result.logs[0].action == "create"
        assert result.logs[0].source == "sql_editor"
        assert result.logs[0].status == "success"
        assert result.logs[0].operation_id
    finally:
        session.close()


def test_vocabulary_sql_cannot_mutate_logs_table(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import mutate_table
    from app.schemas.vocabulary_sql import MutationParams

    session = _make_session(tmp_path)
    try:
        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                mutate_table(
                    MutationParams(
                        table_name="vocabulary_logs",
                        action="create",
                        data={
                            "user_id": 1,
                            "permission_level": "manage",
                            "action": "manual",
                            "table_name": "vocabulary_entries",
                            "affected_rows": 0,
                        },
                    ),
                    current_user=_User(1, role="admin"),
                    db=session,
                )
            )

        assert raised.value.status_code == 400
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_permissions_table_is_not_exposed_through_vocabulary_sql(tmp_path: Path) -> None:
    from app.routes.vocabulary_sql import query_table
    from app.schemas.vocabulary_sql import QueryParams

    session = _make_session(tmp_path)
    try:
        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                query_table(
                    QueryParams(table_name="vocabulary_permissions"),
                    current_user=_User(1, role="admin"),
                    db=session,
                )
            )

        assert raised.value.status_code == 400
    finally:
        session.close()
