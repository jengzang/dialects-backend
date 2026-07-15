import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

os.environ.setdefault("_RUN_TYPE", "WEB")
os.environ.setdefault("AUTO_MIGRATE", "false")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.gzip import GZipMiddleware

from app.common.path import DB_MAPPING
from app.routes.toponyms import router


def create_toponyms_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE single (
            id TEXT PRIMARY KEY,
            standard_name TEXT,
            place_type TEXT,
            place_type_code TEXT,
            area_code TEXT,
            longitude REAL,
            latitude REAL
        );

        CREATE TABLE divisions (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            parent_code TEXT NOT NULL,
            level INTEGER NOT NULL,
            single_cnt INTEGER,
            multi_cnt INTEGER,
            longitude REAL,
            latitude REAL,
            ur_code TEXT
        );
        """
    )
    conn.executemany(
        """
        INSERT INTO single (
            id, standard_name, place_type, place_type_code, area_code, longitude, latitude
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("village-1", "黄村", "农村居民点", "22200", "440100001", 113.1, 23.1),
            ("village-2", "李村", "农村居民点", "22200", "440100002", 113.2, 23.2),
            ("admin-1", "某行政村", "行政村", "21610", "440100003", 113.3, 23.3),
            ("outside-1", "远村", "农村居民点", "22200", "110100001", 116.3, 39.9),
        ],
    )
    conn.executemany(
        """
        INSERT INTO divisions (
            code, name, parent_code, level, single_cnt, multi_cnt, longitude, latitude, ur_code
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("100000", "中华人民共和国", "", 0, 0, 0, None, None, None),
            ("44", "广东省", "100000", 1, 2, 0, 113.2, 23.2, None),
            ("4401", "广州市", "44", 2, 2, 0, 113.3, 23.1, None),
        ],
    )
    conn.commit()
    conn.close()


class ToponymsRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "toponyms.db")
        create_toponyms_db(self.db_path)

        import app.service.toponyms.repository as repository

        self.original_db_path = repository.TOPONYMS_DB_PATH
        repository.TOPONYMS_DB_PATH = self.db_path

        app = FastAPI()
        app.include_router(router, prefix="/api")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        import app.service.toponyms.repository as repository

        repository.TOPONYMS_DB_PATH = self.original_db_path
        self.tmpdir.cleanup()

    def test_toponyms_db_is_not_exposed_through_generic_sql_mapping(self) -> None:
        self.assertNotIn("toponyms", DB_MAPPING)

    def test_main_app_registers_toponyms_routes(self) -> None:
        from app.main import create_main_app

        app = create_main_app()
        paths = {route.path for route in app.routes}

        self.assertIn("/api/toponyms/points", paths)
        self.assertIn("/api/toponyms/names/sample", paths)
        self.assertIn("/api/toponyms/divisions", paths)

    def test_points_endpoint_requires_query(self) -> None:
        response = self.client.get("/api/toponyms/points")

        self.assertEqual(response.status_code, 400)

    def test_points_endpoint_returns_matched_coordinates_and_ids_without_names(self) -> None:
        response = self.client.get(
            "/api/toponyms/points",
            params={"q": "黄", "match_mode": "prefix", "limit": "10"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertFalse(body["truncated"])
        self.assertEqual(
            body["items"][0],
            {"id": "village-1", "longitude": 113.1, "latitude": 23.1},
        )

        serialized = response.text
        self.assertNotIn("name", serialized)
        self.assertNotIn("standard_name", serialized)
        self.assertNotIn("area_code", serialized)
        self.assertNotIn("黄村", serialized)

    def test_points_endpoint_supports_suffix_match_and_unlimited_limit(self) -> None:
        response = self.client.get(
            "/api/toponyms/points",
            params={"q": "村", "match_mode": "suffix", "limit": "0"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 3)
        self.assertFalse(body["truncated"])

    def test_points_endpoint_can_filter_by_bbox_after_name_match(self) -> None:
        response = self.client.get(
            "/api/toponyms/points",
            params={
                "q": "村",
                "match_mode": "suffix",
                "bbox": "113,23,114,24",
                "limit": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual({item["id"] for item in body["items"]}, {"village-1", "village-2"})

    def test_names_endpoint_returns_only_name_strings_without_ids_or_coordinates(self) -> None:
        response = self.client.get(
            "/api/toponyms/names/sample",
            params={"q": "黄", "match_mode": "prefix", "limit": "10"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": ["黄村"]})
        serialized = response.text
        self.assertNotIn("village-1", serialized)
        self.assertNotIn("longitude", serialized)
        self.assertNotIn("latitude", serialized)

    def test_divisions_endpoint_omits_centroid_coordinates(self) -> None:
        response = self.client.get(
            "/api/toponyms/divisions",
            params={"parent_code": "44"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"items": [{"code": "4401", "name": "广州市", "level": 2, "single_count": 2}]},
        )
        self.assertNotIn("longitude", response.text)
        self.assertNotIn("latitude", response.text)

    def test_names_endpoint_supports_contains_exact_suffix_and_unlimited_limit(self) -> None:
        response = self.client.get(
            "/api/toponyms/names/sample",
            params={"q": "村", "match_mode": "contains", "limit": "0"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": ["李村", "远村", "黄村"]})

        exact_response = self.client.get(
            "/api/toponyms/names/sample",
            params={"q": "黄村", "match_mode": "exact"},
        )
        self.assertEqual(exact_response.json(), {"items": ["黄村"]})

        suffix_response = self.client.get(
            "/api/toponyms/names/sample",
            params={"q": "村", "match_mode": "suffix", "limit": "0"},
        )
        self.assertEqual(suffix_response.json(), {"items": ["李村", "远村", "黄村"]})

    def test_points_endpoint_uses_gzip_when_client_accepts_gzip(self) -> None:
        app = FastAPI()
        app.add_middleware(GZipMiddleware, minimum_size=1)
        app.include_router(router, prefix="/api")
        client = TestClient(app)

        response = client.get(
            "/api/toponyms/points",
            params={"q": "村", "match_mode": "contains", "limit": "0"},
            headers={"Accept-Encoding": "gzip"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-encoding"), "gzip")
        self.assertEqual(response.json()["count"], 3)


if __name__ == "__main__":
    unittest.main()
