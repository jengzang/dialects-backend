import sqlite3
from pathlib import Path

import pytest

from app.service.notes import parse_notes_search_fields, query_notes


@pytest.fixture
def notes_db(tmp_path: Path) -> Path:
    path = tmp_path / "dialects_user.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE notes (
                簡稱 TEXT,
                漢字 TEXT,
                音節 TEXT,
                聲母 TEXT,
                韻母 TEXT,
                聲調 TEXT,
                註釋 TEXT
            )
            """
        )
        conn.execute("CREATE INDEX idx_notes_abbr ON notes(簡稱)")
        conn.execute(
            "CREATE VIRTUAL TABLE notes_fts USING fts5(註釋, content='', columnsize=0, tokenize='unicode61')"
        )
        rows = [
            (1, "甲地", "甲", "pa%", "p", "a", "1", "pa 文 白 共"),
            (2, "甲地", "甲", "pb", "p", "b", "1", "文 白 共"),
            (3, "乙地", "乙", "pa", "p", "a", "2", "白讀 共"),
            (4, "乙地", "丙", "xx", "x", "x", "3", "文"),
            (5, "乙地", "丁", "sentinel", "s", "e", "4", "_"),
            (6, "乙地", "戊", "sentinel", "s", "e", "4", "-"),
            (7, "乙地", "己", "dup", "d", "u", "5", "重 複"),
            (8, "乙地", "己", "dup", "d", "u", "5", "重 複"),
        ]
        conn.executemany(
            "INSERT INTO notes(rowid, 簡稱, 漢字, 音節, 聲母, 韻母, 聲調, 註釋) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.executemany(
            "INSERT INTO notes_fts(rowid, 註釋) VALUES (?, ?)",
            [(row[0], row[-1]) for row in rows],
        )
    return path


@pytest.fixture
def query_db(tmp_path: Path) -> Path:
    path = tmp_path / "query_user.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE dialects (
                簡稱 TEXT,
                地圖集二分區 TEXT,
                音典分區 TEXT,
                存儲標記 INTEGER,
                市 TEXT,
                縣 TEXT,
                鎮 TEXT,
                行政村 TEXT,
                自然村 TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO dialects(簡稱, 地圖集二分區, 音典分區, 存儲標記) VALUES (?, ?, ?, ?)",
            [
                ("甲地", "地圖-甲", "音典-甲", 1),
                ("乙地", "地圖-乙", "音典-乙", 1),
            ],
        )
    return path


def search(notes_db: Path, query_db: Path, **overrides):
    params = {
        "q": "共",
        "search_fields": ["detail"],
        "locations": None,
        "regions": None,
        "region_mode": "yindian",
        "page": 1,
        "page_size": 50,
        "notes_db_path": notes_db,
        "query_db_path": query_db,
    }
    params.update(overrides)
    return query_notes(**params)


def test_detail_search_matches_one_and_two_character_queries(notes_db, query_db):
    one_character = search(notes_db, query_db, q="文")
    two_characters = search(notes_db, query_db, q="文白")

    assert [item["id"] for item in one_character["items"]] == [1, 2, 4]
    assert [item["id"] for item in two_characters["items"]] == [1, 2]


def test_ipa_search_treats_percent_as_literal(notes_db, query_db):
    result = search(
        notes_db,
        query_db,
        q="pa%",
        search_fields=["pronunciation"],
    )

    assert [item["ipa"] for item in result["items"]] == ["pa%"]


def test_all_and_empty_fields_search_each_supported_field_once(notes_db, query_db):
    all_fields = search(notes_db, query_db, q="pa", search_fields=["all"])
    empty_fields = search(notes_db, query_db, q="pa", search_fields=[])

    assert parse_notes_search_fields(["all"]) == {"detail", "pronunciation"}
    assert parse_notes_search_fields([]) == {"detail", "pronunciation"}
    assert [item["id"] for item in all_fields["items"]] == [1, 3]
    assert [item["id"] for item in empty_fields["items"]] == [1, 3]


def test_duplicate_source_rows_are_retained_in_rowid_order(notes_db, query_db):
    result = search(notes_db, query_db, q="重複")

    assert [item["id"] for item in result["items"]] == [7, 8]
    assert result["total"] == 2


def test_pagination_and_sentinel_filtering(notes_db, query_db):
    first_page = search(notes_db, query_db, page_size=2)
    second_page = search(notes_db, query_db, page=2, page_size=2)
    sentinel_result = search(
        notes_db,
        query_db,
        q="sentinel",
        search_fields=["pronunciation"],
    )

    assert [item["id"] for item in first_page["items"]] == [1, 2]
    assert [item["id"] for item in second_page["items"]] == [3]
    assert first_page["total"] == 3
    assert sentinel_result["items"] == []


def test_blank_scope_searches_all_locations(notes_db, query_db):
    result = search(notes_db, query_db, q="文白", locations=None, regions=None)

    assert [item["location_name"] for item in result["items"]] == ["甲地", "甲地"]


def test_regions_expand_in_each_partition_mode(notes_db, query_db):
    map_result = search(
        notes_db,
        query_db,
        regions=["地圖-乙"],
        region_mode="map",
    )
    yindian_result = search(
        notes_db,
        query_db,
        regions=["音典-甲"],
        region_mode="yindian",
    )

    assert [item["id"] for item in map_result["items"]] == [3]
    assert [item["id"] for item in yindian_result["items"]] == [1, 2]


def test_explicit_locations_and_regions_are_combined(notes_db, query_db):
    result = search(
        notes_db,
        query_db,
        locations=["甲地"],
        regions=["音典-乙"],
    )

    assert [item["id"] for item in result["items"]] == [1, 2, 3]


def test_scope_that_resolves_to_nothing_does_not_fall_back_to_all_locations(notes_db, query_db):
    result = search(notes_db, query_db, locations=["不存在"])

    assert result == {"items": [], "total": 0, "page": 1, "page_size": 50}


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"q": " "}, "q is required"),
        ({"search_fields": ["location"]}, "Unsupported search_fields"),
        ({"page": 0}, "page must be at least 1"),
        ({"page_size": 201}, "page_size cannot exceed 200"),
    ],
)
def test_invalid_search_parameters_are_rejected(notes_db, query_db, params, message):
    with pytest.raises(ValueError, match=message):
        search(notes_db, query_db, **params)
