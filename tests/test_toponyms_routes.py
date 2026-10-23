import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

os.environ.setdefault("_RUN_TYPE", "WEB")
os.environ.setdefault("AUTO_MIGRATE", "false")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.gzip import GZipMiddleware

from app.common.path import ADMIN_ONLY_DBS, DB_MAPPING
from app.routes.toponyms import router
from app.service.toponyms.config import MAX_DETAIL_IDS, MAX_NAME_LIMIT


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

        CREATE TABLE multi (
            id TEXT PRIMARY KEY,
            standard_name TEXT,
            place_type TEXT,
            place_type_code TEXT,
            area_code TEXT,
            coordinates BLOB
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
            ("village-1b", "黄屋", "农村居民点", "22200", "440100001", 113.15, 23.15),
            ("village-2", "李村", "农村居民点", "22200", "440100002", 113.2, 23.2),
            ("admin-1", "某行政村", "行政村", "21610", "440100003", 113.3, 23.3),
            ("outside-1", "远村", "农村居民点", "22200", "110100001", 116.3, 39.9),
        ],
    )
    conn.executemany(
        """
        INSERT INTO multi (
            id, standard_name, place_type, place_type_code, area_code, coordinates
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("multi-1", "黄路", "主干路", "23512", "440100002", b"line"),
            ("multi-2", "广东河", "河流", "25100", "440100001", b"line"),
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
            ("11", "北京市", "100000", 1, 1, 0, 116.4, 39.9, None),
            ("1101", "北京市", "11", 2, 1, 0, 116.4, 39.9, None),
            ("110100", "北京市辖区", "1101", 3, 1, 0, 116.4, 39.9, None),
            ("110100001", "东城街道", "110100", 4, 1, 0, 116.4, 39.9, None),
            ("44", "广东省", "100000", 1, 2, 0, 113.2, 23.2, None),
            ("4401", "广州市", "44", 2, 2, 0, 113.3, 23.1, None),
            ("440100", "广州市辖区", "4401", 3, 2, 0, 113.3, 23.1, None),
            ("440100001", "越秀街道", "440100", 4, 1, 0, 113.1, 23.1, None),
            ("440100002", "荔湾街道", "440100", 4, 1, 0, 113.2, 23.2, None),
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

    def test_toponyms_db_is_admin_only_in_generic_sql_mapping(self) -> None:
        self.assertIn("toponyms", DB_MAPPING)
        self.assertIn("toponyms", ADMIN_ONLY_DBS)

    def test_main_app_registers_toponyms_routes(self) -> None:
        from app.main import create_main_app

        app = create_main_app()
        paths = {route.path for route in app.routes}

        self.assertIn("/api/toponyms/points", paths)
        self.assertIn("/api/toponyms/search", paths)
        self.assertIn("/api/toponyms/names", paths)
        self.assertIn("/api/toponyms/details", paths)
        self.assertNotIn("/api/toponyms/names/", paths)
        self.assertNotIn("/api/toponyms/names/sample", paths)
        self.assertIn("/api/toponyms/divisions", paths)

    def test_points_endpoint_requires_query(self) -> None:
        response = self.client.get("/api/toponyms/points")

        self.assertEqual(response.status_code, 400)

    def test_queries_preserve_unlimited_contract(self) -> None:
        for endpoint in ("points", "search", "names"):
            response = self.client.get(
                f"/api/toponyms/{endpoint}",
                params={"q": "村", "match_mode": "contains", "limit": 0},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["items"]), 3)
            if endpoint != "names":
                self.assertFalse(response.json()["truncated"])
                self.assertEqual(response.json()["count"], 3)

    def test_unlimited_queries_stream_every_row_without_truncation(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT INTO single VALUES (?,?,?,?,?,?,?)",
                [(f"bulk-{i:06}", f"批量村{i:06}", "农村居民点", "22200",
                  "440100001", 113.0, 23.0) for i in range(12001)],
            )
        for endpoint in ("points", "search", "names"):
            response = self.client.get(f"/api/toponyms/{endpoint}", params={
                "q": "批量村", "match_mode": "contains", "limit": 0,
            })
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(len(body["items"]), 12001)
            self.assertEqual(response.headers.get("x-toponyms-stream"), "1")
            if endpoint != "names":
                self.assertEqual(body["count"], 12001)
                self.assertFalse(body["truncated"])

    def test_unlimited_matching_matrix_equals_original_sql(self) -> None:
        from scripts.toponyms.ensure_indexes import ensure_toponyms_indexes
        ensure_toponyms_indexes(self.db_path)
        modes = [("exact", "黄村", "=", "黄村"), ("prefix", "黄", "LIKE", "黄%"),
                 ("suffix", "村", "LIKE", "%村"), ("contains", "村", "LIKE", "%村%"),
                 ("contains", "不存在", "LIKE", "%不存在%"),
                 ("contains", "%", "LIKE", "%%%")]
        for mode, query, operator, pattern in modes:
            for boxed in (False, True):
                for codes in (["22200"], ["22200", "21610", "23512"]):
                    placeholders = ",".join("?" for _ in codes)
                    where = f"place_type_code IN ({placeholders}) AND standard_name {operator} ?"
                    values = [*codes, pattern]
                    if boxed:
                        where += " AND longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ?"
                        values += [113, 114, 23, 24]
                    params = {"q": query, "match_mode": mode, "limit": 0,
                              "place_type_code": ",".join(codes)}
                    if boxed:
                        params["bbox"] = "113,23,114,24"
                    with sqlite3.connect(self.db_path) as conn:
                        expected_points = conn.execute(
                            f"SELECT id,longitude,latitude FROM single WHERE {where} ORDER BY id", values
                        ).fetchall()
                        expected_names = conn.execute(
                            f"SELECT DISTINCT standard_name FROM single WHERE {where} "
                            "AND TRIM(COALESCE(standard_name,''))<>'' ORDER BY standard_name", values
                        ).fetchall()
                        single = f"SELECT id,standard_name AS name FROM single WHERE {where}"
                        sql = single if boxed else single + f" UNION ALL SELECT id,standard_name AS name FROM multi WHERE {where}"
                        expected_search = conn.execute(
                            "SELECT id,name FROM (" + sql + ") ORDER BY name,id",
                            values if boxed else values * 2,
                        ).fetchall()
                    for endpoint, expected in (("points", expected_points),
                                                ("search", expected_search), ("names", expected_names)):
                        response = self.client.get(f"/api/toponyms/{endpoint}", params=params)
                        self.assertEqual(response.status_code, 200, (endpoint, mode, response.text))
                        body = response.json()
                        actual = ([(name,) for name in body["items"]] if endpoint == "names"
                                  else [tuple(item.values()) for item in body["items"]])
                        self.assertEqual(actual, expected, (endpoint, mode, boxed, codes))
                        if endpoint != "names":
                            self.assertEqual(body["count"], len(expected))
                            self.assertFalse(body["truncated"])
                        if endpoint == "search":
                            self.assertNotIn("next", body)

    def test_unlimited_response_survives_logging_and_gzip_middleware(self) -> None:
        from unittest.mock import AsyncMock, Mock
        from app.service.logging.middleware import traffic_logging as logging
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.add_middleware(GZipMiddleware, minimum_size=1)
        app.add_middleware(logging.RequestLogMiddleware)
        @app.middleware("http")
        async def passthrough(request, call_next):
            return await call_next(request)
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("INSERT INTO single VALUES (?,?,?,?,?,?,?)", [
                (f"gzip-{i:06}", f"流式村{i:06}", "农村居民点", "22200",
                 "440100001", 113., 23.) for i in range(6001)
            ])
        with (
            patch.object(logging, "should_capture_diagnostic_path", return_value=True),
            patch.object(logging, "should_record_auth_usage", return_value=False),
            patch.object(logging, "get_db", return_value=iter([Mock()])),
            patch.object(logging, "get_current_user_for_middleware", new=AsyncMock(return_value=None)),
            patch.object(logging, "update_count"),
            patch.object(logging, "_log_params_if_needed", new=AsyncMock()),
            patch.object(logging, "enqueue_diagnostic_event"),
        ):
            response = TestClient(app).get("/api/toponyms/points", params={
                "q": "流式村", "match_mode": "contains", "limit": 0,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-encoding"], "gzip")
        self.assertEqual(response.json()["count"], 6001)
        self.assertEqual(len(response.json()["items"]), 6001)
        self.assertFalse(response.json()["truncated"])

    def test_tree_never_loads_all_divisions(self) -> None:
        from contextlib import contextmanager
        from app.service.toponyms.resources import connection
        statements = []
        @contextmanager
        def traced(path, **kwargs):
            with connection(path, **kwargs) as conn:
                conn.set_trace_callback(statements.append)
                yield conn
        with patch("app.service.toponyms.repository.connection", traced):
            response = self.client.get("/api/toponyms/names", params={
                "q": "村", "match_mode": "contains", "include_division_tree": "true",
            })
        division_queries = [sql for sql in statements if "FROM divisions" in sql]
        self.assertTrue(division_queries)
        self.assertTrue(all("WHERE code IN" in sql for sql in division_queries))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "full")

    def test_tree_probe_does_not_claim_exact_total(self) -> None:
        with patch("app.service.toponyms.repository.TOPONYM_NAME_TREE_FULL_THRESHOLD", 1):
            response = self.client.get("/api/toponyms/names", params={
                "q": "村", "match_mode": "contains", "include_division_tree": "true",
            })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["filtered_count"])
        self.assertFalse(body["count_exact"])
        self.assertEqual(body["count_lower_bound"], 2)

    def test_points_covering_path_preserves_results_and_order(self) -> None:
        from contextlib import contextmanager
        from scripts.toponyms.ensure_indexes import ensure_toponyms_indexes
        from app.service.toponyms.resources import connection
        from app.service.toponyms import repository
        ensure_toponyms_indexes(self.db_path)
        statements = []
        @contextmanager
        def traced(path, **kwargs):
            with connection(path, **kwargs) as conn:
                conn.set_trace_callback(statements.append)
                yield conn
        for mode, pattern in (("contains", "%村%"), ("suffix", "%村")):
            with sqlite3.connect(self.db_path) as conn:
                expected = conn.execute(
                    "SELECT id,longitude,latitude FROM single WHERE place_type_code IN (?,?) "
                    "AND standard_name LIKE ? ORDER BY id LIMIT 3",
                    ("22200", "21610", pattern),
                ).fetchall()
            with patch.object(repository, "connection", traced):
                items, truncated = repository.list_points_by_name(
                    query="村", match_mode=mode, limit=2, place_type_codes=["22200", "21610"],
                )
            self.assertEqual([tuple(item.values()) for item in items], expected[:2])
            self.assertTrue(truncated)
        point_sql = next(sql for sql in statements if "INDEXED BY idx_single_type_name_id" in sql)
        with sqlite3.connect(self.db_path) as conn:
            plan = [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + point_sql)]
        self.assertTrue(any("COVERING INDEX idx_single_type_name_id" in row for row in plan))

    def test_tree_loads_level_five_ancestors_and_unknown_paths_are_empty(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO divisions (code,name,parent_code,level) VALUES (?,?,?,?)",
                         ("440100001001", "村级区划", "440100001", 5))
            conn.execute("UPDATE single SET area_code=? WHERE id='village-1'", ("440100001001",))
        response = self.client.get("/api/toponyms/names", params={
            "q": "黄村", "match_mode": "exact", "include_division_tree": "true",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("村级区划", response.text)
        missing = self.client.get("/api/toponyms/names", params={
            "q": "村", "include_division_tree": "true", "parent_path": "不存在省",
        })
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.json()["children"], [])

    def test_resource_errors_have_explicit_http_status(self) -> None:
        from app.service.toponyms.resources import QueryBusy, QueryTimedOut
        for error, status in ((QueryBusy("busy"), 503), (QueryTimedOut("deadline"), 504)):
            with patch("app.routes.toponyms.run_query", side_effect=error):
                response = self.client.get("/api/toponyms/search", params={"q": "黄"})
            self.assertEqual(response.status_code, status)

    def test_points_endpoint_returns_matched_coordinates_and_ids_without_names(self) -> None:
        response = self.client.get(
            "/api/toponyms/points",
            params={"q": "黄", "match_mode": "prefix", "limit": "10"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 2)
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

    def test_points_endpoint_can_filter_by_place_type_code(self) -> None:
        default_response = self.client.get(
            "/api/toponyms/points",
            params={"q": "某行政村", "match_mode": "exact", "limit": "10"},
        )
        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(default_response.json()["items"], [])

        response = self.client.get(
            "/api/toponyms/points",
            params={
                "q": "某行政村",
                "match_mode": "exact",
                "place_type_code": "21610",
                "limit": "10",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(
            body["items"][0],
            {"id": "admin-1", "longitude": 113.3, "latitude": 23.3},
        )
        self.assertNotIn("某行政村", response.text)

    def test_points_endpoint_supports_suffix_match_and_unlimited_limit(self) -> None:
        response = self.client.get(
            "/api/toponyms/points",
            params={"q": "村", "match_mode": "suffix", "limit": "0"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 3)
        self.assertFalse(body["truncated"])

    def test_query_limit_uses_configured_upper_bound(self) -> None:
        accepted = self.client.get(
            "/api/toponyms/names",
            params={"q": "黄", "match_mode": "prefix", "limit": str(MAX_NAME_LIMIT)},
        )
        self.assertEqual(accepted.status_code, 200)

        rejected = self.client.get(
            "/api/toponyms/names",
            params={"q": "黄", "match_mode": "prefix", "limit": str(MAX_NAME_LIMIT + 1)},
        )
        self.assertEqual(rejected.status_code, 422)

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

    def test_search_endpoint_returns_single_and_multi_ids_with_names_only(self) -> None:
        response = self.client.get(
            "/api/toponyms/search",
            params=[
                ("q", "黄"),
                ("match_mode", "prefix"),
                ("place_type_code", "22200"),
                ("place_type_code", "23512"),
                ("limit", "0"),
            ],
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 3)
        self.assertFalse(body["truncated"])
        self.assertEqual(
            body["items"],
            [
                {"id": "village-1b", "name": "黄屋"},
                {"id": "village-1", "name": "黄村"},
                {"id": "multi-1", "name": "黄路"},
            ],
        )
        serialized = response.text
        self.assertNotIn("longitude", serialized)
        self.assertNotIn("latitude", serialized)
        self.assertNotIn("area_code", serialized)
        self.assertNotIn("place_type_code", serialized)
        self.assertNotIn("coordinates", serialized)

    def test_search_endpoint_can_optionally_include_area_and_type_codes(self) -> None:
        response = self.client.get(
            "/api/toponyms/search",
            params={
                "q": "黄路",
                "match_mode": "exact",
                "place_type_code": "23512",
                "include_area_code": "true",
                "include_place_type_code": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "items": [
                    {
                        "id": "multi-1",
                        "name": "黄路",
                        "area_code": "440100002",
                        "place_type_code": "23512",
                    }
                ],
                "count": 1,
                "truncated": False,
            },
        )
        self.assertNotIn("longitude", response.text)
        self.assertNotIn("coordinates", response.text)

    def test_search_endpoint_can_filter_by_area_code_scope(self) -> None:
        descendants_response = self.client.get(
            "/api/toponyms/search",
            params={
                "q": "村",
                "match_mode": "suffix",
                "area_code": "44",
                "area_scope": "descendants",
                "limit": "0",
            },
        )

        self.assertEqual(descendants_response.status_code, 200)
        self.assertEqual(
            {item["id"] for item in descendants_response.json()["items"]},
            {"village-1", "village-2"},
        )

        exact_response = self.client.get(
            "/api/toponyms/search",
            params={
                "q": "黄",
                "match_mode": "prefix",
                "area_code": "440100001",
                "area_scope": "exact",
                "limit": "0",
            },
        )

        self.assertEqual(exact_response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in exact_response.json()["items"]],
            ["village-1b", "village-1"],
        )

    def test_names_endpoint_returns_only_name_strings_without_ids_or_coordinates(self) -> None:
        response = self.client.get(
            "/api/toponyms/names",
            params={"q": "黄", "match_mode": "prefix", "limit": "10"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": ["黄屋", "黄村"]})
        serialized = response.text
        self.assertNotIn("village-1", serialized)
        self.assertNotIn("longitude", serialized)
        self.assertNotIn("latitude", serialized)

    def test_names_endpoint_can_filter_by_place_type_code(self) -> None:
        default_response = self.client.get(
            "/api/toponyms/names",
            params={"q": "某行政村", "match_mode": "exact", "limit": "10"},
        )
        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(default_response.json(), {"items": []})

        response = self.client.get(
            "/api/toponyms/names",
            params={
                "q": "某行政村",
                "match_mode": "exact",
                "place_type_code": "21610",
                "limit": "10",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": ["某行政村"]})
        serialized = response.text
        self.assertNotIn("admin-1", serialized)
        self.assertNotIn("longitude", serialized)
        self.assertNotIn("latitude", serialized)

    def test_names_endpoint_can_filter_by_bbox_without_returning_coordinates(self) -> None:
        response = self.client.get(
            "/api/toponyms/names",
            params={
                "q": "村",
                "match_mode": "suffix",
                "bbox": "113,23,114,24",
                "limit": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": ["李村", "黄村"]})
        self.assertNotIn("longitude", response.text)
        self.assertNotIn("latitude", response.text)

    def test_names_endpoint_can_return_division_tree_without_ids_or_coordinates(self) -> None:
        response = self.client.get(
            "/api/toponyms/names",
            params={
                "q": "村",
                "match_mode": "suffix",
                "limit": "0",
                "include_division_tree": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body,
            {
                "mode": "full",
                "items": [
                    {
                        "name": "北京市",
                        "level": 1,
                        "names": [],
                        "children": [
                            {
                                "name": "北京市",
                                "level": 2,
                                "names": [],
                                "children": [
                                    {
                                        "name": "北京市辖区",
                                        "level": 3,
                                        "names": [],
                                        "children": [
                                            {
                                                "name": "东城街道",
                                                "level": 4,
                                                "names": ["远村"],
                                                "children": [],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "name": "广东省",
                        "level": 1,
                        "names": [],
                        "children": [
                            {
                                "name": "广州市",
                                "level": 2,
                                "names": [],
                                "children": [
                                    {
                                        "name": "广州市辖区",
                                        "level": 3,
                                        "names": [],
                                        "children": [
                                            {
                                                "name": "越秀街道",
                                                "level": 4,
                                                "names": ["黄村"],
                                                "children": [],
                                            },
                                            {
                                                "name": "荔湾街道",
                                                "level": 4,
                                                "names": ["李村"],
                                                "children": [],
                                            },
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                ],
                "levels": 4,
            },
        )
        serialized = response.text
        self.assertNotIn("village-1", serialized)
        self.assertNotIn("area_code", serialized)
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

    def test_names_tree_falls_back_to_lazy_bootstrap_when_result_is_large(self) -> None:
        with patch("app.service.toponyms.repository.TOPONYM_NAME_TREE_FULL_THRESHOLD", 2):
            response = self.client.get(
                "/api/toponyms/names",
                params={
                    "q": "村",
                    "match_mode": "suffix",
                    "include_division_tree": "true",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "lazy_fallback")
        self.assertEqual(body["reason"], "tree_result_too_large")
        self.assertEqual(body["threshold"], 2)
        self.assertIsNone(body["filtered_count"])
        self.assertFalse(body["count_exact"])
        self.assertEqual(body["count_lower_bound"], 3)
        self.assertEqual(body["levels"], 4)
        self.assertEqual(
            body["lazy_bootstrap"],
            [
                {
                    "name": "北京市",
                    "level": 1,
                    "children": [{"name": "北京市", "level": 2}],
                },
                {
                    "name": "广东省",
                    "level": 1,
                    "children": [{"name": "广州市", "level": 2}],
                },
            ],
        )
        serialized = response.text
        self.assertNotIn("village-1", serialized)
        self.assertNotIn("area_code", serialized)
        self.assertNotIn("longitude", serialized)

    def test_names_tree_lazy_parent_path_returns_children_then_leaf_names_with_pagination(self) -> None:
        child_response = self.client.get(
            "/api/toponyms/names",
            params=[
                ("q", "村"),
                ("match_mode", "suffix"),
                ("include_division_tree", "true"),
                ("parent_path", "广东省"),
            ],
        )

        self.assertEqual(child_response.status_code, 200)
        self.assertEqual(
            child_response.json(),
            {
                "mode": "lazy",
                "level": 2,
                "parent_path": ["广东省"],
                "children": [{"name": "广州市", "level": 2}],
                "has_more": False,
            },
        )

        leaf_response = self.client.get(
            "/api/toponyms/names",
            params=[
                ("q", "黄"),
                ("match_mode", "prefix"),
                ("include_division_tree", "true"),
                ("parent_path", "广东省"),
                ("parent_path", "广州市"),
                ("parent_path", "广州市辖区"),
                ("parent_path", "越秀街道"),
                ("page", "1"),
                ("page_size", "1"),
            ],
        )

        self.assertEqual(leaf_response.status_code, 200)
        self.assertEqual(
            leaf_response.json(),
            {
                "mode": "lazy",
                "level": 4,
                "parent_path": ["广东省", "广州市", "广州市辖区", "越秀街道"],
                "names": ["黄屋"],
                "page": 1,
                "page_size": 1,
                "has_more": True,
            },
        )

    def test_names_tree_lazy_handles_division_paths_that_skip_level_three(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.executemany(
            """
            INSERT INTO divisions (
                code, name, parent_code, level, single_cnt, multi_cnt, longitude, latitude, ur_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("4419", "东莞市", "44", 2, 2, 0, 113.7, 23.0, None),
                ("441900114", "黄江镇", "4419", 4, 1, 0, 114.0, 22.9, None),
                ("441900115", "清溪镇", "4419", 4, 1, 0, 114.1, 22.8, None),
            ],
        )
        conn.executemany(
            """
            INSERT INTO single (
                id, standard_name, place_type, place_type_code, area_code, longitude, latitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("dongguan-huangjiang-1", "黄江村", "农村居民点", "22200", "441900114", 114.0, 22.9),
                ("dongguan-qingxi-1", "黄田村", "农村居民点", "22200", "441900115", 114.1, 22.8),
            ],
        )
        conn.commit()
        conn.close()

        children_response = self.client.get(
            "/api/toponyms/names",
            params=[
                ("q", "黄"),
                ("match_mode", "prefix"),
                ("include_division_tree", "true"),
                ("parent_path", "广东省"),
                ("parent_path", "东莞市"),
                ("place_type_code", "22200"),
                ("place_type_code", "21610"),
                ("place_type_code", "27610"),
            ],
        )

        self.assertEqual(children_response.status_code, 200)
        self.assertEqual(
            children_response.json(),
            {
                "mode": "lazy",
                "level": 4,
                "parent_path": ["广东省", "东莞市"],
                "children": [
                    {"name": "黄江镇", "level": 4},
                    {"name": "清溪镇", "level": 4},
                ],
                "has_more": False,
            },
        )

        leaf_response = self.client.get(
            "/api/toponyms/names",
            params=[
                ("q", "黄"),
                ("match_mode", "prefix"),
                ("include_division_tree", "true"),
                ("parent_path", "广东省"),
                ("parent_path", "东莞市"),
                ("parent_path", "黄江镇"),
                ("page", "1"),
                ("page_size", "100"),
                ("place_type_code", "22200"),
                ("place_type_code", "21610"),
                ("place_type_code", "27610"),
            ],
        )

        self.assertEqual(leaf_response.status_code, 200)
        self.assertEqual(
            leaf_response.json(),
            {
                "mode": "lazy",
                "level": 4,
                "parent_path": ["广东省", "东莞市", "黄江镇"],
                "names": ["黄江村"],
                "page": 1,
                "page_size": 100,
                "has_more": False,
            },
        )

    def test_details_endpoint_returns_full_records_for_limited_ids(self) -> None:
        response = self.client.get(
            "/api/toponyms/details",
            params={"ids": "village-1,admin-1,multi-1,missing-id"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "items": [
                    {
                        "id": "village-1",
                        "name": "黄村",
                        "place_type": "农村居民点",
                        "place_type_code": "22200",
                        "longitude": 113.1,
                        "latitude": 23.1,
                        "division_path": [
                            {"name": "广东省", "level": 1},
                            {"name": "广州市", "level": 2},
                            {"name": "广州市辖区", "level": 3},
                            {"name": "越秀街道", "level": 4},
                        ],
                    },
                    {
                        "id": "admin-1",
                        "name": "某行政村",
                        "place_type": "行政村",
                        "place_type_code": "21610",
                        "longitude": 113.3,
                        "latitude": 23.3,
                        "division_path": [],
                    },
                    {
                        "id": "multi-1",
                        "name": "黄路",
                        "place_type": "主干路",
                        "place_type_code": "23512",
                        "longitude": None,
                        "latitude": None,
                        "division_path": [
                            {"name": "广东省", "level": 1},
                            {"name": "广州市", "level": 2},
                            {"name": "广州市辖区", "level": 3},
                            {"name": "荔湾街道", "level": 4},
                        ],
                    },
                ],
                "count": 3,
            },
        )
        self.assertNotIn("area_code", response.text)
        self.assertNotIn("coordinates", response.text)

    def test_details_endpoint_rejects_more_than_configured_ids(self) -> None:
        ids = ",".join(f"id-{index}" for index in range(MAX_DETAIL_IDS + 1))

        response = self.client.get("/api/toponyms/details", params={"ids": ids})

        self.assertEqual(response.status_code, 400)
        self.assertIn(str(MAX_DETAIL_IDS), response.text)

    def test_names_endpoint_supports_contains_exact_suffix_and_unlimited_limit(self) -> None:
        response = self.client.get(
            "/api/toponyms/names",
            params={"q": "村", "match_mode": "contains", "limit": "0"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": ["李村", "远村", "黄村"]})

        exact_response = self.client.get(
            "/api/toponyms/names",
            params={"q": "黄村", "match_mode": "exact"},
        )
        self.assertEqual(exact_response.json(), {"items": ["黄村"]})

        suffix_response = self.client.get(
            "/api/toponyms/names",
            params={"q": "村", "match_mode": "suffix", "limit": "0"},
        )
        self.assertEqual(suffix_response.json(), {"items": ["李村", "远村", "黄村"]})

    def test_names_sample_endpoint_is_removed(self) -> None:
        response = self.client.get(
            "/api/toponyms/names/sample",
            params={"q": "黄", "match_mode": "prefix", "limit": "10"},
        )

        self.assertEqual(response.status_code, 404)

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
