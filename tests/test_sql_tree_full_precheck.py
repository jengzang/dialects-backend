import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.sql.sql_schemas import FullTreeParams
from app.sql.sql_tree_routes import get_full_tree


class _FakeUser:
    role = "admin"


class _TrackingCursor:
    def __init__(self, cursor, executed_sql):
        self._cursor = cursor
        self._executed_sql = executed_sql

    def execute(self, sql, params=()):
        self._executed_sql.append(sql)
        return self._cursor.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _TrackingConnection:
    def __init__(self, conn, executed_sql):
        self._conn = conn
        self._executed_sql = executed_sql

    def cursor(self, *args, **kwargs):
        return _TrackingCursor(self._conn.cursor(*args, **kwargs), self._executed_sql)

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._conn.__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class SqlTreeFullPrecheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_tree_prechecks_count_and_directly_falls_back_to_lazy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "tree.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE toponyms (
                        id INTEGER PRIMARY KEY,
                        standard_name TEXT,
                        place_type_code TEXT,
                        province TEXT,
                        city TEXT,
                        district TEXT,
                        town TEXT,
                        coords TEXT
                    )
                    """
                )
                conn.executemany(
                    "INSERT INTO toponyms (standard_name, place_type_code, province, city, district, town, coords) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        (f"村{i}", "12100", "广东省", "广州市", "天河区", "石牌街道", "0,0")
                        for i in range(5001)
                    ],
                )

            params = FullTreeParams(
                db_key="villages_admin",
                table_name="toponyms",
                level_columns=[3, 4, 5, 1],
                data_columns=[],
                filters={2: ["12100"], 3: ["广东省"]},
            )

            real_connect = sqlite3.connect
            executed_sql: list[str] = []

            def tracking_connect(*args, **kwargs):
                conn = real_connect(*args, **kwargs)
                conn.row_factory = sqlite3.Row
                return _TrackingConnection(conn, executed_sql)

            with (
                patch("app.sql.sql_tree_routes.DB_MAPPING", {"villages_admin": str(db_path)}),
                patch("app.sql.choose_db.DB_MAPPING", {"villages_admin": str(db_path)}),
                patch("app.sql.db_pool.sqlite3.connect", side_effect=tracking_connect),
            ):
                result = await get_full_tree(params, user=_FakeUser(), auth_db=None)

        self.assertEqual(result["mode"], "lazy_fallback")
        self.assertEqual(result["reason"], "full_tree_count_threshold_exceeded")
        self.assertEqual(result["filtered_count"], 5001)
        self.assertEqual(result["threshold"], 5000)
        self.assertIn("广东省", result["lazy_bootstrap"])
        self.assertTrue(any(sql.startswith("SELECT COUNT(*)") for sql in executed_sql))
        self.assertFalse(
            any('SELECT DISTINCT "province", "city", "district", "town"' in sql for sql in executed_sql),
            executed_sql,
        )


if __name__ == "__main__":
    unittest.main()
