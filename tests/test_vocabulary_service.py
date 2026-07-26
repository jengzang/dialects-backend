import json
from pathlib import Path

import pytest
from docx import Document
from fastapi import HTTPException

from app.service.vocabulary.database import create_vocabulary_engine_and_session, migrate_vocabulary_database
from app.service.vocabulary.models import (
    Base,
    VocabularyEntry,
    VocabularyLocation,
    VocabularyLog,
    VocabularyPermission,
)
from app.service.vocabulary.permissions import get_effective_permission_level
from app.service.vocabulary.query import (
    query_vocabulary_map_items,
    query_vocabulary_items,
    query_vocabulary_location_options,
    query_vocabulary_map_points,
    query_vocabulary_standard_words,
)
from app.service.vocabulary.service import import_vocabulary_upload
from app.service.vocabulary.service import preview_vocabulary_upload


class _User:
    def __init__(self, user_id: int, role: str = "user"):
        self.id = user_id
        self.role = role


def _make_session(tmp_path: Path):
    engine, session_factory = create_vocabulary_engine_and_session(tmp_path / "vocabulary.db")
    Base.metadata.create_all(bind=engine)
    return session_factory()


def _docx_bytes(tmp_path: Path, paragraphs: list[str], filename: str = "upload.docx") -> bytes:
    docx_path = tmp_path / filename
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(docx_path)
    return docx_path.read_bytes()


def test_admin_permission_resolves_to_manage(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        assert get_effective_permission_level(session, _User(1, role="admin")) == "manage"
    finally:
        session.close()


def test_vocabulary_tables_store_user_id_without_username(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        for table in (VocabularyEntry, VocabularyLocation, VocabularyPermission):
            assert "user_id" in table.__table__.columns
            assert "username" not in table.__table__.columns
        for table in (VocabularyEntry, VocabularyLocation, VocabularyPermission):
            assert "created_at" not in table.__table__.columns
            assert "updated_at" not in table.__table__.columns
        assert "raw_location_json" not in VocabularyLocation.__table__.columns
    finally:
        session.close()


def test_vocabulary_sqlite_connections_wait_for_busy_writes(tmp_path: Path) -> None:
    engine, _ = create_vocabulary_engine_and_session(tmp_path / "vocabulary.db")
    raw_conn = engine.raw_connection()
    try:
        timeout_ms = raw_conn.execute("PRAGMA busy_timeout").fetchone()[0]
    finally:
        raw_conn.close()

    assert timeout_ms == 10000


def test_migration_backfills_and_constrains_vocabulary_log_operation_columns(tmp_path: Path) -> None:
    engine, _ = create_vocabulary_engine_and_session(tmp_path / "legacy_vocabulary.db")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE vocabulary_logs (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission_level VARCHAR(20) NOT NULL,
                action VARCHAR(50) NOT NULL,
                table_name VARCHAR(100) NOT NULL,
                target_scope TEXT,
                affected_rows INTEGER NOT NULL,
                payload_json TEXT,
                created_at DATETIME NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO vocabulary_logs (
                user_id, permission_level, action, table_name,
                target_scope, affected_rows, payload_json, created_at
            )
            VALUES (7, 'edit', 'update', 'vocabulary_entries', 'legacy row', 3, '{}', '2026-07-26 00:00:00')
            """
        )

    migrate_vocabulary_database(engine)

    with engine.connect() as conn:
        column_info = {
            row[1]: {"notnull": bool(row[3]), "type": row[2]}
            for row in conn.exec_driver_sql('PRAGMA table_info("vocabulary_logs")').fetchall()
        }
        row = conn.exec_driver_sql(
            "SELECT operation_id, source, status FROM vocabulary_logs WHERE id = 1"
        ).fetchone()

    assert column_info["operation_id"]["notnull"]
    assert column_info["source"]["notnull"]
    assert column_info["status"]["notnull"]
    assert row == ("legacy-1", "legacy", "success")


def test_migration_removes_legacy_location_raw_json_column(tmp_path: Path) -> None:
    engine, _ = create_vocabulary_engine_and_session(tmp_path / "legacy_locations.db")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE vocabulary_locations (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                location_name VARCHAR(200) NOT NULL,
                coordinates VARCHAR(200) NOT NULL,
                province VARCHAR(100),
                city VARCHAR(100),
                county VARCHAR(100),
                town VARCHAR(100),
                administrative_village VARCHAR(200),
                natural_village VARCHAR(200),
                yindian_region VARCHAR(200),
                atlas_region VARCHAR(200),
                raw_location_json TEXT
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO vocabulary_locations (
                user_id, location_name, coordinates, province, city,
                county, town, administrative_village, natural_village,
                yindian_region, atlas_region, raw_location_json
            )
            VALUES (
                7, '息烽', '106.734862,27.09809', '贵州', '贵阳',
                '息烽', '', '', '', '中上江-荆益-川黔',
                '西南官话-川黔片-成渝小片', '{"location_name":"息烽"}'
            )
            """
        )

    migrate_vocabulary_database(engine)

    with engine.connect() as conn:
        columns = [
            row[1]
            for row in conn.exec_driver_sql('PRAGMA table_info("vocabulary_locations")').fetchall()
        ]
        row = conn.exec_driver_sql(
            "SELECT user_id, location_name, coordinates, province, city, county "
            "FROM vocabulary_locations"
        ).fetchone()

    assert "raw_location_json" not in columns
    assert row == (7, "息烽", "106.734862,27.09809", "贵州", "贵阳", "息烽")


def test_edit_permission_resolves_to_edit(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(
            VocabularyPermission(
                user_id=7,
                permission_level="edit",
            )
        )
        session.commit()

        assert get_effective_permission_level(session, _User(7)) == "edit"
    finally:
        session.close()


def test_missing_permission_raises_403(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        with pytest.raises(HTTPException) as raised:
            get_effective_permission_level(session, _User(7))
    finally:
        session.close()

    assert raised.value.status_code == 403


def test_import_replaces_current_users_location_entries_and_keeps_other_users(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(
            VocabularyPermission(
                user_id=7,
                permission_level="edit",
            )
        )
        session.add_all(
            [
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="旧词",
                    local_expression="旧讲法",
                    ipa="old1",
                    notes="old",
                ),
                VocabularyEntry(
                    user_id=8,
                    location_name="息烽",
                    standard_word="别人词",
                    local_expression="别人讲法",
                    ipa="other1",
                    notes="other",
                ),
            ]
        )
        session.add(
            VocabularyLocation(
                user_id=7,
                location_name="息烽",
                coordinates="old",
            )
        )
        session.commit()

        csv_content = (
            "written,vocabulary,ipa,notes\n"
            "太阳,日头,ȵit2 tʰəu2,常用\n"
            "月亮,月光,ŋye2 kuaŋ1,\n"
        ).encode("utf-8")
        result = import_vocabulary_upload(
            session=session,
            user=_User(7),
            filename="upload.csv",
            content=csv_content,
            location_payload=json.dumps(
                {
                    "location_name": "息烽",
                    "coordinates": "106.73,27.10",
                    "省": "贵州",
                },
                ensure_ascii=False,
            ),
            parser_mode="table",
        )

        rows = session.query(VocabularyEntry).order_by(
            VocabularyEntry.user_id.asc(),
            VocabularyEntry.standard_word.asc(),
        ).all()
        location = session.query(VocabularyLocation).filter(
            VocabularyLocation.user_id == 7,
            VocabularyLocation.location_name == "息烽",
        ).one()

        assert result.imported_count == 2
        assert result.deleted_existing_count == 1
        assert [(row.user_id, row.standard_word) for row in rows] == [
            (7, "太阳"),
            (7, "月亮"),
            (8, "别人词"),
        ]
        assert location.coordinates == "106.73,27.10"
        assert location.province == "贵州"
    finally:
        session.close()


def test_import_upserts_existing_location_metadata(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.add(
            VocabularyLocation(
                user_id=7,
                location_name="息烽",
                coordinates="old",
                province="旧省",
            )
        )
        session.commit()

        result = import_vocabulary_upload(
            session=session,
            user=_User(7),
            filename="upload.csv",
            content=(
                "written,vocabulary,ipa,notes\n"
                "太阳,日头,ȵit2 tʰəu2,常用\n"
            ).encode("utf-8"),
            location_payload=json.dumps(
                {
                    "location_name": "息烽",
                    "coordinates": "106.73,27.10",
                    "省": "贵州",
                    "市": "贵阳",
                },
                ensure_ascii=False,
            ),
            parser_mode="table",
        )

        locations = session.query(VocabularyLocation).all()
        assert result.location_id == locations[0].id
        assert len(locations) == 1
        assert locations[0].coordinates == "106.73,27.10"
        assert locations[0].province == "贵州"
        assert locations[0].city == "贵阳"
    finally:
        session.close()


def test_preview_upload_reports_import_counts_without_changing_database(tmp_path: Path) -> None:
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
                notes="old",
            )
        )
        session.commit()

        csv_content = (
            "written,vocabulary,ipa,notes\n"
            "太阳,日头,ȵit2 tʰəu2,常用\n"
            "月亮,月光,ŋye2 kuaŋ1,\n"
        ).encode("utf-8")
        result = preview_vocabulary_upload(
            session=session,
            user=_User(7),
            filename="upload.csv",
            content=csv_content,
            location_payload=json.dumps(
                {
                    "location_name": "息烽",
                    "coordinates": "106.73,27.10",
                },
                ensure_ascii=False,
            ),
            parser_mode="table",
        )

        assert result.success is True
        assert result.location_name == "息烽"
        assert result.permission_level == "edit"
        assert result.parsed_count == 2
        assert result.would_delete_existing_count == 1
        assert result.skipped_count == 0
        assert result.errors == []
        assert result.parser_mode == "table"
        assert session.query(VocabularyEntry).count() == 1
        assert session.query(VocabularyLocation).count() == 0
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_preview_upload_returns_parse_errors_without_writing_log(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.commit()

        csv_content = (
            "written,vocabulary,ipa,notes\n"
            "太阳,日头,,缺音标\n"
        ).encode("utf-8")
        result = preview_vocabulary_upload(
            session=session,
            user=_User(7),
            filename="upload.csv",
            content=csv_content,
            location_payload=json.dumps(
                {
                    "location_name": "息烽",
                    "coordinates": "106.73,27.10",
                },
                ensure_ascii=False,
            ),
            parser_mode="table",
        )

        assert result.success is False
        assert result.parsed_count == 0
        assert result.would_delete_existing_count == 0
        assert result.errors
        assert "ipa" in result.errors[0]
        assert session.query(VocabularyEntry).count() == 0
        assert session.query(VocabularyLocation).count() == 0
        assert session.query(VocabularyLog).count() == 0
    finally:
        session.close()


def test_import_upload_accepts_real_docx_whitespace_mode(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.commit()

        result = import_vocabulary_upload(
            session=session,
            user=_User(7),
            filename="upload.docx",
            content=_docx_bytes(
                tmp_path,
                [
                    "太阳\n日头\nȵit2 tʰəu2\n常用",
                    "月亮\n月光\nŋye2 kuaŋ1",
                ],
            ),
            location_payload=json.dumps(
                {
                    "location_name": "息烽",
                    "coordinates": "106.73,27.10",
                },
                ensure_ascii=False,
            ),
            parser_mode="doc_whitespace",
        )

        rows = session.query(VocabularyEntry).order_by(VocabularyEntry.id.asc()).all()
        assert result.parser_mode == "doc_whitespace"
        assert result.imported_count == 2
        assert [(row.standard_word, row.local_expression, row.ipa, row.notes) for row in rows] == [
            ("太阳", "日头", "ȵit2 tʰəu2", "常用"),
            ("月亮", "月光", "ŋye2 kuaŋ1", ""),
        ]
    finally:
        session.close()


def test_import_upload_accepts_real_docx_bracket_mode(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.commit()

        result = import_vocabulary_upload(
            session=session,
            user=_User(7),
            filename="upload.docx",
            content=_docx_bytes(
                tmp_path,
                [
                    "太阳（日头）[ȵit2 tʰəu2]{常用}",
                    "月亮(月光)[ŋye2 kuaŋ1]",
                ],
                filename="upload-bracket.docx",
            ),
            location_payload=json.dumps(
                {
                    "location_name": "息烽",
                    "coordinates": "106.73,27.10",
                },
                ensure_ascii=False,
            ),
            parser_mode="doc_bracket",
        )

        rows = session.query(VocabularyEntry).order_by(VocabularyEntry.id.asc()).all()
        assert result.parser_mode == "doc_bracket"
        assert result.imported_count == 2
        assert [(row.standard_word, row.local_expression, row.ipa, row.notes) for row in rows] == [
            ("太阳", "日头", "ȵit2 tʰəu2", "常用"),
            ("月亮", "月光", "ŋye2 kuaŋ1", ""),
        ]
    finally:
        session.close()


def test_import_vocabulary_upload_writes_log(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(VocabularyPermission(user_id=7, permission_level="edit"))
        session.commit()

        csv_content = (
            "written,vocabulary,ipa,notes\n"
            "太阳,日头,ȵit2 tʰəu2,常用\n"
        ).encode("utf-8")
        import_vocabulary_upload(
            session=session,
            user=_User(7),
            filename="upload.csv",
            content=csv_content,
            location_payload=json.dumps(
                {
                    "location_name": "息烽",
                    "coordinates": "106.73,27.10",
                },
                ensure_ascii=False,
            ),
            parser_mode="table",
        )

        log = session.query(VocabularyLog).one()
        assert log.user_id == 7
        assert log.permission_level == "edit"
        assert log.source == "upload"
        assert log.action == "import"
        assert log.status == "success"
        assert log.operation_id
        assert log.table_name == "vocabulary_entries"
        assert log.affected_rows == 1
        assert "location_name = 息烽" in log.target_scope
    finally:
        session.close()


def test_import_log_records_replaced_entries_for_recovery(tmp_path: Path) -> None:
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
                notes="old",
                informations="old-info",
                source_filename="old.csv",
            )
        )
        session.commit()

        import_vocabulary_upload(
            session=session,
            user=_User(7),
            filename="upload.csv",
            content=(
                "written,vocabulary,ipa,notes\n"
                "太阳,日头,ȵit2 tʰəu2,常用\n"
            ).encode("utf-8"),
            location_payload=json.dumps(
                {
                    "location_name": "息烽",
                    "coordinates": "106.73,27.10",
                },
                ensure_ascii=False,
            ),
            parser_mode="table",
        )

        payload = json.loads(session.query(VocabularyLog).one().payload_json)
        assert payload["deleted_entries"][0]["standard_word"] == "旧词"
        assert payload["deleted_entries"][0]["local_expression"] == "旧讲法"
        assert payload["deleted_entries"][0]["source_filename"] == "old.csv"
        assert payload["before_location"] is None
        assert payload["after_location"]["location_name"] == "息烽"
        assert payload["after_location"]["coordinates"] == "106.73,27.10"
        assert payload["deleted_entries_omitted"] is False
        assert payload["deleted_entries_log_limit"] == 500
        assert payload["rollback_supported"] is False
    finally:
        session.close()


def test_query_vocabulary_items_searches_content_fields_and_paginates(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.7400,27.0900",
                    province="贵州",
                    city="贵阳",
                    county="息烽",
                ),
                VocabularyLocation(
                    user_id=7,
                    location_name="天柱竹林",
                    coordinates="109.2070,26.9090",
                    province="贵州",
                    city="黔东南",
                    county="天柱",
                ),
            ]
        )
        session.add_all(
            [
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="zɿ2 tʰəu2",
                    notes="太阳",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="天柱竹林",
                    standard_word="开日头",
                    local_expression="开日头",
                    ipa="kʰai1 ɤ3 tiao2",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="月亮",
                    local_expression="月光",
                    ipa="ŋye2 kuaŋ1",
                    notes="",
                    informations="",
                ),
            ]
        )
        session.commit()

        result = query_vocabulary_items(session=session, q="日头", page=1, page_size=1)

        assert result.total == 2
        assert result.page == 1
        assert result.page_size == 1
        assert not hasattr(result.items[0], "id")
        assert result.items[0].standard_word == "太阳"
        assert result.items[0].local_expression == "日头"
        assert result.items[0].ipa == "zɿ2 tʰəu2"
        assert result.items[0].notes == "太阳"
        assert result.items[0].informations == ""
        assert result.items[0].location_name == "息烽"
        assert result.items[0].location_label == "贵州 / 贵阳 / 息烽"
    finally:
        session.close()


def test_query_vocabulary_items_does_not_search_location_by_default(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(
            VocabularyLocation(
                user_id=7,
                location_name="息烽",
                coordinates="106.7400,27.0900",
                province="贵州",
                city="贵阳",
                county="息烽",
            )
        )
        session.add(
            VocabularyEntry(
                user_id=7,
                location_name="息烽",
                standard_word="太阳",
                local_expression="日头",
                ipa="zɿ2 tʰəu2",
                notes="",
                informations="",
            )
        )
        session.commit()

        result = query_vocabulary_items(session=session, q="息烽")

        assert result.total == 0
        assert result.items == []
    finally:
        session.close()


def test_query_vocabulary_items_filters_locations_independently(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.7400,27.0900",
                    province="贵州",
                    city="贵阳",
                    county="息烽",
                ),
                VocabularyLocation(
                    user_id=7,
                    location_name="天柱竹林",
                    coordinates="109.2070,26.9090",
                    province="贵州",
                    city="黔东南",
                    county="天柱",
                ),
            ]
        )
        session.add_all(
            [
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="zɿ2 tʰəu2",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="天柱竹林",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="ɤ3 tiao2",
                    notes="",
                    informations="",
                ),
            ]
        )
        session.commit()

        result = query_vocabulary_items(session=session, q="日头", locations=["天柱"])

        assert result.total == 1
        assert result.items[0].location_name == "天柱竹林"
    finally:
        session.close()


def test_query_vocabulary_map_points_aggregates_locations_without_pagination(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.7400,27.0900",
                    province="贵州",
                    city="贵阳",
                    county="息烽",
                ),
                VocabularyLocation(
                    user_id=7,
                    location_name="天柱竹林",
                    coordinates="109.2070,26.9090",
                    province="贵州",
                    city="黔东南",
                    county="天柱",
                ),
                VocabularyLocation(
                    user_id=7,
                    location_name="无坐标点",
                    coordinates="unknown",
                    province="贵州",
                ),
            ]
        )
        session.add_all(
            [
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="zɿ2 tʰəu2",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="红日",
                    local_expression="日头",
                    ipa="zɿ2 tʰəu2",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="天柱竹林",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="ɤ3 tiao2",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="无坐标点",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="月亮",
                    local_expression="月光",
                    ipa="ŋye2 kuaŋ1",
                    notes="",
                    informations="",
                ),
            ]
        )
        session.commit()

        result = query_vocabulary_map_points(session=session, q="日头")

        assert result.total_entries == 4
        assert result.total_points == 2
        assert result.omitted_without_coordinates == 1
        assert [(point.location_name, point.entry_count) for point in result.points] == [
            ("息烽", 2),
            ("天柱竹林", 1),
        ]
        assert result.points[0].location_label == "贵州 / 贵阳 / 息烽"
        assert result.points[0].longitude == 106.74
        assert result.points[0].latitude == 27.09
    finally:
        session.close()


def test_query_vocabulary_location_options_returns_distinct_public_names(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.7400,27.0900",
                    province="贵州",
                    city="贵阳",
                    county="息烽",
                ),
                VocabularyLocation(
                    user_id=8,
                    location_name="息烽",
                    coordinates="106.7400,27.0900",
                    province="贵州",
                    city="贵阳",
                    county="息烽",
                ),
                VocabularyLocation(
                    user_id=7,
                    location_name="天柱竹林",
                    coordinates="109.2070,26.9090",
                    province="贵州",
                    city="黔东南",
                    county="天柱",
                ),
            ]
        )
        session.commit()

        result = query_vocabulary_location_options(session=session)

        assert result.total == 2
        assert [
            (location.location_name, location.location_label)
            for location in result.locations
        ] == [
            ("天柱竹林", "贵州 / 黔东南 / 天柱"),
            ("息烽", "贵州 / 贵阳 / 息烽"),
        ]
        assert not hasattr(result.locations[0], "user_id")
        assert not hasattr(result.locations[0], "coordinates")
    finally:
        session.close()


def test_query_vocabulary_standard_words_returns_all_distinct_without_filters(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="ipa1",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=8,
                    location_name="广州",
                    standard_word="太阳",
                    local_expression="太阳",
                    ipa="ipa2",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="月亮",
                    local_expression="月光",
                    ipa="ipa3",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="",
                    local_expression="空",
                    ipa="ipa4",
                    notes="",
                    informations="",
                ),
            ]
        )
        session.commit()

        result = query_vocabulary_standard_words(session=session)

        assert result.total == 2
        assert [
            (row.standard_word, row.entry_count, row.location_count)
            for row in result.standard_words
        ] == [
            ("太阳", 2, 2),
            ("月亮", 1, 1),
        ]
    finally:
        session.close()


def test_query_vocabulary_standard_words_filters_by_q_and_locations(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.7400,27.0900",
                    province="贵州",
                    city="贵阳",
                    county="息烽",
                ),
                VocabularyLocation(
                    user_id=7,
                    location_name="天柱竹林",
                    coordinates="109.2070,26.9090",
                    province="贵州",
                    city="黔东南",
                    county="天柱",
                ),
            ]
        )
        session.add_all(
            [
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="ipa1",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="天柱竹林",
                    standard_word="太阳",
                    local_expression="太阳",
                    ipa="ipa2",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="月亮",
                    local_expression="月光",
                    ipa="ipa3",
                    notes="",
                    informations="",
                ),
            ]
        )
        session.commit()

        result = query_vocabulary_standard_words(
            session=session,
            q="日头",
            search_fields=["headword"],
            locations=["息烽"],
        )

        assert result.total == 1
        assert result.standard_words[0].standard_word == "太阳"
        assert result.standard_words[0].entry_count == 1
        assert result.standard_words[0].location_count == 1
    finally:
        session.close()


def test_query_vocabulary_map_items_returns_details_for_selected_standard_words(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add_all(
            [
                VocabularyLocation(
                    user_id=7,
                    location_name="息烽",
                    coordinates="106.7400,27.0900",
                    province="贵州",
                    city="贵阳",
                    county="息烽",
                ),
                VocabularyLocation(
                    user_id=7,
                    location_name="天柱竹林",
                    coordinates="109.2070,26.9090",
                    province="贵州",
                    city="黔东南",
                    county="天柱",
                ),
                VocabularyLocation(
                    user_id=7,
                    location_name="无坐标点",
                    coordinates="unknown",
                    province="贵州",
                ),
            ]
        )
        session.add_all(
            [
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="ipa1",
                    notes="常用",
                    informations="info1",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="天柱竹林",
                    standard_word="太阳",
                    local_expression="太阳",
                    ipa="ipa2",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="无坐标点",
                    standard_word="太阳",
                    local_expression="日头",
                    ipa="ipa3",
                    notes="",
                    informations="",
                ),
                VocabularyEntry(
                    user_id=7,
                    location_name="息烽",
                    standard_word="月亮",
                    local_expression="月光",
                    ipa="ipa4",
                    notes="",
                    informations="",
                ),
            ]
        )
        session.commit()

        result = query_vocabulary_map_items(session=session, standard_words=["太阳"])

        assert result.total_entries == 3
        assert result.total_points == 2
        assert result.omitted_without_coordinates == 1
        assert [(point.location_name, point.entry_count) for point in result.points] == [
            ("息烽", 1),
            ("天柱竹林", 1),
        ]
        assert result.points[0].longitude == 106.74
        assert result.points[0].latitude == 27.09
        assert result.points[0].items[0].standard_word == "太阳"
        assert result.points[0].items[0].local_expression == "日头"
        assert result.points[0].items[0].ipa == "ipa1"
        assert result.points[0].items[0].notes == "常用"
        assert result.points[0].items[0].informations == "info1"
    finally:
        session.close()
