from pathlib import Path

import pytest

from app.service.notes import query_notes


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTES_DB = PROJECT_ROOT / "data" / "dialects_user.db"
QUERY_DB = PROJECT_ROOT / "data" / "query_user.db"

pytestmark = pytest.mark.skipif(
    not NOTES_DB.exists() or not QUERY_DB.exists(),
    reason="runtime notes and query databases are required for this contract test",
)


def test_runtime_databases_support_one_character_and_top_level_region_searches():
    one_character = query_notes(
        q="文",
        search_fields=["detail"],
        locations=None,
        regions=None,
        region_mode="yindian",
        page=1,
        page_size=1,
        notes_db_path=NOTES_DB,
        query_db_path=QUERY_DB,
    )
    top_level_region = query_notes(
        q="文",
        search_fields=["detail"],
        locations=None,
        regions=["閩"],
        region_mode="yindian",
        page=1,
        page_size=1,
        notes_db_path=NOTES_DB,
        query_db_path=QUERY_DB,
    )

    for result in (one_character, top_level_region):
        assert result["page"] == 1
        assert result["page_size"] == 1
        assert isinstance(result["total"], int)
        assert len(result["items"]) <= 1
        if result["items"]:
            assert set(result["items"][0]) == {
                "id",
                "location_name",
                "character",
                "ipa",
                "notes",
            }
