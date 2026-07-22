import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class VillagesMLSchemaRuntimeTests(unittest.TestCase):
    def test_configured_database_key_installs_logical_views(self) -> None:
        from app.villagesML.dependencies import get_db_connection

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "alternate.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE alt_villages (
                        alt_id TEXT,
                        alt_name TEXT,
                        alt_city TEXT,
                        alt_county TEXT,
                        alt_township TEXT,
                        alt_lng TEXT,
                        alt_lat TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO alt_villages
                    VALUES ('v_1', '水口', '广州市', '番禺区', '石楼镇', '113.1', '22.9')
                    """
                )

            test_config = {
                "alternate": {
                    "path_key": "alternate_village",
                    "tables": {
                        "villages": {
                            "name": "alt_villages",
                            "logical_name": "广东省自然村_预处理",
                            "columns": {
                                "village_id": "alt_id",
                                "name": "alt_name",
                                "committee": "alt_name",
                                "city": "alt_city",
                                "county": "alt_county",
                                "township": "alt_township",
                                "longitude": "alt_lng",
                                "latitude": "alt_lat",
                            },
                        }
                    },
                }
            }

            with (
                patch("app.villagesML.schema_config.VILLAGES_DATABASES", test_config),
                patch("app.villagesML.schema_runtime.DB_MAPPING", {"alternate_village": str(db_path)}),
            ):
                with get_db_connection("alternate") as db:
                    row = db.execute(
                        """
                        SELECT
                            village_id,
                            自然村_规范名,
                            市级,
                            区县级,
                            乡镇级,
                            longitude,
                            latitude
                        FROM 广东省自然村_预处理
                        """
                    ).fetchone()

        self.assertEqual(row["village_id"], "v_1")
        self.assertEqual(row["自然村_规范名"], "水口")
        self.assertEqual(row["市级"], "广州市")

    def test_unknown_database_key_is_rejected(self) -> None:
        from app.villagesML.schema_runtime import resolve_db_path

        with self.assertRaisesRegex(ValueError, "Unknown villagesML database key"):
            resolve_db_path("missing")

    def test_default_village_key_uses_mapping_not_env_override(self) -> None:
        from app.villagesML.schema_runtime import resolve_db_path

        with (
            patch.dict("os.environ", {"VILLAGES_DB_PATH": "/tmp/custom-villages.db"}),
            patch("app.villagesML.schema_runtime.DB_MAPPING", {"village": "/tmp/mapped-villages.db"}),
        ):
            self.assertEqual(resolve_db_path("village"), "/tmp/mapped-villages.db")

    def test_schema_helpers_cover_village_data_identifiers(self) -> None:
        from app.villagesML.schema_runtime import configured_table_list, qcolumn, qtable

        self.assertEqual(qtable("village", "villages"), '"广东省自然村_预处理"')
        self.assertEqual(qcolumn("village", "villages", "name"), '"自然村_规范名"')
        self.assertEqual(qcolumn("village", "villages", "committee"), '"村委会"')
        self.assertEqual(qcolumn("village", "villages", "dialect"), '"方言分布"')
        self.assertEqual(qtable("village", "villages_raw"), '"广东省自然村"')
        self.assertEqual(qcolumn("village", "villages_raw", "committee"), '"行政村"')
        self.assertEqual(qcolumn("village", "villages_raw", "dialect"), '"方言分布"')
        self.assertEqual(qtable("village", "village_ngrams"), '"village_ngrams"')
        self.assertEqual(qcolumn("village", "village_ngrams", "committee"), '"村委会"')
        self.assertEqual(qtable("village", "sqlite_master"), '"sqlite_master"')
        self.assertEqual(qtable("village", "regional_basic_stats"), '"regional_basic_stats"')
        self.assertEqual(qcolumn("village", "regional_basic_stats", "avg_name_length"), '"avg_name_length"')
        self.assertEqual(qcolumn("village", "regional_basic_stats", "region_key"), '"region_key"')
        self.assertEqual(qcolumn("village", "query_policy_config", "profile"), '"profile"')
        self.assertEqual(qcolumn("village", "city_aggregates", "total_villages"), '"total_villages"')
        self.assertEqual(qcolumn("village", "region_vectors", "region_id"), '"region_id"')
        self.assertIn(
            "regional_ngram_frequency",
            configured_table_list("village", "database_statistics"),
        )

    def test_raw_village_logical_view_uses_current_physical_columns(self) -> None:
        from app.villagesML.schema_runtime import install_schema_views

        with sqlite3.connect(":memory:") as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                CREATE TABLE physical_raw_villages (
                    自然村 TEXT,
                    行政村 TEXT,
                    市级 TEXT,
                    区县级 TEXT,
                    乡镇级 TEXT,
                    longitude REAL,
                    latitude REAL,
                    方言分布 TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO physical_raw_villages
                VALUES ('水口', '水口行政村', '广州市', '从化区', '太平镇', 113.1, 23.1, '粤语')
                """
            )

            test_config = {
                "raw_test": {
                    "path_key": "raw_test",
                    "tables": {
                        "villages_raw": {
                            "name": "physical_raw_villages",
                            "logical_name": "villages_raw_view",
                            "columns": {
                                "name": "自然村",
                                "committee": "行政村",
                                "city": "市级",
                                "county": "区县级",
                                "township": "乡镇级",
                                "longitude": "longitude",
                                "latitude": "latitude",
                                "dialect": "方言分布",
                            },
                        }
                    },
                }
            }

            with patch("app.villagesML.schema_config.VILLAGES_DATABASES", test_config):
                install_schema_views(conn, "raw_test")
                row = conn.execute(
                    """
                    SELECT
                        自然村,
                        行政村,
                        市级,
                        区县级,
                        乡镇级,
                        longitude,
                        latitude,
                        方言分布
                    FROM villages_raw_view
                    """
                ).fetchone()

        self.assertEqual(row["自然村"], "水口")
        self.assertEqual(row["行政村"], "水口行政村")
        self.assertEqual(row["方言分布"], "粤语")

    def test_villages_routes_expose_dbpath_query_parameter(self) -> None:
        from fastapi import FastAPI

        from app.villagesML import setup_villages_routes

        app = FastAPI()
        setup_villages_routes(app)

        openapi = app.openapi()
        params = openapi["paths"]["/api/villages/village/search"]["get"]["parameters"]

        self.assertTrue(
            any(param["name"] == "dbpath" and param["in"] == "query" for param in params),
            params,
        )


if __name__ == "__main__":
    unittest.main()
