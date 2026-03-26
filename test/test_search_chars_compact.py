from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.connection import get_db
from app.service.core import search_chars as search_chars_service
from app.sql.db_selector import get_dialects_db, get_query_db


def _load_search_router_module():
    route_file = Path(__file__).resolve().parents[1] / "app" / "routes" / "core" / "search.py"
    spec = importlib.util.spec_from_file_location("test_search_router_module", route_file)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_empty_query_db(path: Path) -> None:
    sqlite3.connect(path).close()


def _create_dialects_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE dialects (
            "簡稱" TEXT,
            "漢字" TEXT,
            "音節" TEXT,
            "聲母" TEXT,
            "韻母" TEXT,
            "聲調" TEXT,
            "註釋" TEXT,
            "多音字" INTEGER
        )
        """
    )
    cursor.executemany(
        """
        INSERT INTO dialects ("簡稱", "漢字", "音節", "聲母", "韻母", "聲調", "註釋", "多音字")
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("廣州", "行", "haang4", "h", "aang", "4", "走", 1),
            ("番禺", "行", "hang4", "h", "ang", "4", "路", 1),
            ("廣州", "行", "hong4", "h", "ong", "4", "行列", 1),
        ],
    )
    conn.commit()
    conn.close()


def _create_characters_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE characters (
            "攝" TEXT,
            "呼" TEXT,
            "等" TEXT,
            "韻" TEXT,
            "入" TEXT,
            "調" TEXT,
            "清濁" TEXT,
            "系" TEXT,
            "組" TEXT,
            "母" TEXT,
            "部位" TEXT,
            "方式" TEXT,
            "漢字" TEXT,
            "釋義" TEXT,
            "多聲母" TEXT,
            "多等" TEXT,
            "多韻" TEXT,
            "多調" TEXT,
            "多地位標記" TEXT
        )
        """
    )
    cursor.executemany(
        """
        INSERT INTO characters (
            "攝", "呼", "等", "韻", "入", "調", "清濁", "系", "組", "母", "部位", "方式",
            "漢字", "釋義", "多聲母", "多等", "多韻", "多調", "多地位標記"
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("宕", "開", "一", "唐", "舒", "平", "全清", "匣", "曉", "匣", "軟腭", "擦", "行", "", "0", "0", "0", "0", "1"),
            ("梗", "開", "二", "庚", "舒", "去", "全清", "匣", "曉", "匣", "軟腭", "擦", "行", "", "0", "0", "0", "0", "1"),
        ],
    )

    cursor.execute(
        """
        CREATE TABLE old_chinese (
            "漢字" TEXT,
            "原始音標" TEXT,
            "聲調" TEXT,
            "聲母" TEXT,
            "韻母" TEXT,
            "韻部" TEXT,
            "聲母組" TEXT,
            "r介音" TEXT,
            "非三等" TEXT,
            "諧聲域" TEXT,
            "音" TEXT,
            "見詩經韻" TEXT,
            "見其他韻" TEXT,
            "總出現次數" TEXT,
            "先秦字頻（歸一化）" TEXT,
            "少見詞出處" TEXT,
            "見西周" TEXT,
            "西周字頻（歸一化）" TEXT,
            "釋義" TEXT,
            "注釋" TEXT,
            "多地位標記" TEXT
        )
        """
    )
    cursor.executemany(
        """
        INSERT INTO old_chinese (
            "漢字", "原始音標", "聲調", "聲母", "韻母", "韻部", "聲母組", "r介音", "非三等", "諧聲域",
            "音", "見詩經韻", "見其他韻", "總出現次數", "先秦字頻（歸一化）", "少見詞出處",
            "見西周", "西周字頻（歸一化）", "釋義", "注釋", "多地位標記"
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("行", "", "平", "g", "ang", "陽", "K", "", "", "", "", "", "", "", "", "", "", "", "", "", "1"),
            ("行", "", "去", "g", "ang", "陽", "K", "", "", "", "", "", "", "", "", "", "", "", "", "", "1"),
        ],
    )
    conn.commit()
    conn.close()


def test_search_characters_compact_moves_char_meta_out_of_rows(tmp_path: Path, monkeypatch):
    query_db_path = tmp_path / "query_user.db"
    dialects_db_path = tmp_path / "dialects_user.db"
    characters_db_path = tmp_path / "characters.db"

    _create_empty_query_db(query_db_path)
    _create_dialects_db(dialects_db_path)
    _create_characters_db(characters_db_path)

    monkeypatch.setattr(search_chars_service, "CHARACTERS_DB_PATH", str(characters_db_path))

    legacy = search_chars_service.search_characters(
        chars=["行"],
        locations=["廣州", "番禺"],
        regions=None,
        db_path=str(dialects_db_path),
        query_db_path=str(query_db_path),
        response_mode="legacy",
    )
    compact = search_chars_service.search_characters(
        chars=["行"],
        locations=["廣州", "番禺"],
        regions=None,
        db_path=str(dialects_db_path),
        query_db_path=str(query_db_path),
        response_mode="compact",
    )

    assert isinstance(legacy, list)
    assert len(legacy) == 2
    assert "positions" in legacy[0]
    assert "old_position" in legacy[0]

    assert compact == {
        "result": [
            {
                "char": "行",
                "音节": ["haang4", "hong4"],
                "location": "廣州",
                "notes": ["走", "行列"],
            },
            {
                "char": "行",
                "音节": ["hang4", "haang4", "hong4"],
                "location": "番禺",
                "notes": ["路", "走", "行列"],
            },
        ],
        "char_meta": {
            "行": {
                "positions": legacy[0]["positions"],
                "old_position": legacy[0]["old_position"],
            }
        },
    }


def test_search_chars_route_exposes_compact_shape(monkeypatch):
    module = _load_search_router_module()
    app = FastAPI()
    app.include_router(module.router, prefix="/api")

    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_dialects_db] = lambda: "unused-dialects.db"
    app.dependency_overrides[get_query_db] = lambda: "unused-query.db"
    app.dependency_overrides[get_current_user] = lambda: None

    captured = {}

    def _fake_match_locations_batch_all(*args, **kwargs):
        return ["廣州"]

    def _fake_search_characters(**kwargs):
        captured["response_mode"] = kwargs["response_mode"]
        if kwargs["response_mode"] == "compact":
            return {
                "result": [{"char": "行", "音节": ["haang4"], "location": "廣州", "notes": ["走"]}],
                "char_meta": {"行": {"positions": ["宕開一唐平"], "old_position": ["陽·ang,K·g·平"]}},
            }
        return [
            {
                "char": "行",
                "音节": ["haang4"],
                "location": "廣州",
                "positions": ["宕開一唐平"],
                "old_position": ["陽·ang,K·g·平"],
                "notes": ["走"],
            }
        ]

    def _fake_search_tones(**kwargs):
        return [{"簡稱": "廣州", "總數據": [], "tones": []}]

    monkeypatch.setattr(module, "match_locations_batch_all", _fake_match_locations_batch_all)
    monkeypatch.setattr(module, "search_characters", _fake_search_characters)
    monkeypatch.setattr(module, "search_tones", _fake_search_tones)

    client = TestClient(app)

    compact_response = client.get(
        "/api/search_chars/",
        params=[("chars", "行"), ("response_mode", "compact")],
    )
    assert compact_response.status_code == 200
    assert compact_response.json() == {
        "result": [{"char": "行", "音节": ["haang4"], "location": "廣州", "notes": ["走"]}],
        "char_meta": {"行": {"positions": ["宕開一唐平"], "old_position": ["陽·ang,K·g·平"]}},
        "tones_result": [{"簡稱": "廣州", "總數據": [], "tones": []}],
    }
    assert captured["response_mode"] == "compact"

    legacy_response = client.get("/api/search_chars/", params=[("chars", "行")])
    assert legacy_response.status_code == 200
    assert legacy_response.json() == {
        "result": [
            {
                "char": "行",
                "音节": ["haang4"],
                "location": "廣州",
                "positions": ["宕開一唐平"],
                "old_position": ["陽·ang,K·g·平"],
                "notes": ["走"],
            }
        ],
        "tones_result": [{"簡稱": "廣州", "總數據": [], "tones": []}],
    }
