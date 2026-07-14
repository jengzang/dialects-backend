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
        self.assertEqual(qtable("village", "village_ngrams"), '"village_ngrams"')
        self.assertEqual(qcolumn("village", "village_ngrams", "committee"), '"村委会"')
        self.assertEqual(qtable("village", "sqlite_master"), '"sqlite_master"')
        self.assertEqual(qcolumn("village", "city_aggregates", "total_villages"), '"total_villages"')
        self.assertEqual(qcolumn("village", "region_vectors", "region_id"), '"region_id"')
        self.assertIn(
            "regional_ngram_frequency",
            configured_table_list("village", "database_statistics"),
        )

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
