import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.service.vocabulary.database import create_vocabulary_engine_and_session
from app.service.vocabulary.models import (
    Base,
    VocabularyEntry,
    VocabularyLocation,
    VocabularyPermission,
)
from app.service.vocabulary.permissions import get_effective_permission_level
from app.service.vocabulary.service import import_vocabulary_upload


class _User:
    def __init__(self, user_id: int, username: str = "user@example.com", role: str = "user"):
        self.id = user_id
        self.username = username
        self.role = role


def _make_session(tmp_path: Path):
    engine, session_factory = create_vocabulary_engine_and_session(tmp_path / "vocabulary.db")
    Base.metadata.create_all(bind=engine)
    return session_factory()


def test_admin_permission_resolves_to_manage(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        assert get_effective_permission_level(session, _User(1, role="admin")) == "manage"
    finally:
        session.close()


def test_edit_permission_resolves_to_edit(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    try:
        session.add(
            VocabularyPermission(
                user_id=7,
                username="editor@example.com",
                permission_level="edit",
            )
        )
        session.commit()

        assert get_effective_permission_level(session, _User(7, "editor@example.com")) == "edit"
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
                username="editor@example.com",
                permission_level="edit",
            )
        )
        session.add_all(
            [
                VocabularyEntry(
                    user_id=7,
                    username="editor@example.com",
                    location_name="息烽",
                    standard_word="旧词",
                    local_expression="旧讲法",
                    ipa="old1",
                    notes="old",
                ),
                VocabularyEntry(
                    user_id=8,
                    username="other@example.com",
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
                username="editor@example.com",
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
            user=_User(7, "editor@example.com"),
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
