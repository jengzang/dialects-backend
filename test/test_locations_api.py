from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.sql.db_selector import get_query_db


def _load_locations_router():
    route_file = Path(__file__).resolve().parents[1] / "app" / "routes" / "geo" / "locations.py"
    spec = importlib.util.spec_from_file_location("test_locations_router_module", route_file)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.router


def _create_query_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE dialects (
            "簡稱" TEXT,
            "語言" TEXT,
            "地圖集二分區" TEXT,
            "音典分區" TEXT,
            "字表來源（母本）" TEXT,
            "經緯度" TEXT,
            "省" TEXT,
            "市" TEXT,
            "縣" TEXT,
            "鎮" TEXT,
            "行政村" TEXT,
            "自然村" TEXT,
            "T1陰平" TEXT,
            "T2陽平" TEXT,
            "T3陰上" TEXT,
            "T4陽上" TEXT,
            "T5陰去" TEXT,
            "T6陽去" TEXT,
            "T7陰入" TEXT,
            "T8陽入" TEXT,
            "T9其他調" TEXT,
            "T10輕聲" TEXT,
            "存儲標記" TEXT
        )
        """
    )
    cursor.executemany(
        """
        INSERT INTO dialects (
            "簡稱", "語言", "地圖集二分區", "音典分區", "字表來源（母本）", "經緯度",
            "省", "市", "縣", "鎮", "行政村", "自然村",
            "T1陰平", "T2陽平", "T3陰上", "T4陽上", "T5陰去",
            "T6陽去", "T7陰入", "T8陽入", "T9其他調", "T10輕聲", "存儲標記"
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "廣州",
                "粵語",
                "粵海片-廣州小片",
                "廣府片-廣州小片",
                "某來源",
                "113.264385,23.129112",
                "廣東",
                "廣州",
                "",
                "",
                "",
                "",
                "55",
                "35",
                "33",
                "21",
                "",
                "",
                "",
                "",
                "",
                "",
                "1",
            ),
            (
                "番禺",
                "粵語",
                "粵海片-廣州小片",
                "廣府片-廣州小片",
                "另一來源",
                "113.384129,22.937244",
                "廣東",
                "廣州",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "0",
            ),
            (
                "",
                "粵語",
                "粵海片-空白小片",
                "廣府片-空白小片",
                "",
                "",
                "廣東",
                "廣州",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "1",
            ),
        ],
    )
    conn.commit()
    conn.close()


def _build_client(query_db_path: str) -> TestClient:
    app = FastAPI()
    locations_router = _load_locations_router()
    app.include_router(locations_router, prefix="/api")
    app.dependency_overrides[get_query_db] = lambda: query_db_path
    return TestClient(app)


def test_location_detail_returns_row_shaped_payload(tmp_path: Path):
    db_path = tmp_path / "query_user.db"
    _create_query_db(db_path)
    client = _build_client(str(db_path))

    response = client.get("/api/locations/detail", params={"name": "廣州"})

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "data": [
            {
                "簡稱": "廣州",
                "語言": "粵語",
                "地圖集二分區": "粵海片-廣州小片",
                "音典分區": "廣府片-廣州小片",
                "字表來源（母本）": "某來源",
                "經緯度": "113.264385,23.129112",
                "省": "廣東",
                "市": "廣州",
                "縣": "",
                "鎮": "",
                "行政村": "",
                "自然村": "",
                "T1陰平": "55",
                "T2陽平": "35",
                "T3陰上": "33",
                "T4陽上": "21",
                "T5陰去": "",
                "T6陽去": "",
                "T7陰入": "",
                "T8陽入": "",
                "T9其他調": "",
                "T10輕聲": "",
            }
        ]
    }


def test_location_detail_returns_empty_list_when_not_found(tmp_path: Path):
    db_path = tmp_path / "query_user.db"
    _create_query_db(db_path)
    client = _build_client(str(db_path))

    response = client.get("/api/locations/detail", params={"name": "不存在"})

    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_location_partitions_returns_minimal_rows_and_skips_empty_names(tmp_path: Path):
    db_path = tmp_path / "query_user.db"
    _create_query_db(db_path)
    client = _build_client(str(db_path))

    response = client.get("/api/locations/partitions")

    assert response.status_code == 200
    assert response.json() == {
        "data": [
            {
                "簡稱": "廣州",
                "語言": "粵語",
                "存儲標記": "1",
                "地圖集二分區": "粵海片-廣州小片",
                "音典分區": "廣府片-廣州小片",
                "省": "廣東",
                "市": "廣州",
                "縣": "",
                "鎮": "",
                "行政村": "",
                "自然村": "",
            },
            {
                "簡稱": "番禺",
                "語言": "粵語",
                "存儲標記": "0",
                "地圖集二分區": "粵海片-廣州小片",
                "音典分區": "廣府片-廣州小片",
                "省": "廣東",
                "市": "廣州",
                "縣": "",
                "鎮": "",
                "行政村": "",
                "自然村": "",
            },
        ]
    }
