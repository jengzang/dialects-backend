import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.sql.sql_routes import get_column_info, get_table_count, query_table
from app.sql.sql_schemas import QueryParams


class _FakeUser:
    role = "admin"


class SqlRoutesThreadOffloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_routes_offload_blocking_db_work_to_thread(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "query.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute('CREATE TABLE items (name TEXT, category TEXT)')
                conn.executemany(
                    'INSERT INTO items VALUES (?, ?)',
                    [("甲", "a"), ("乙", "a"), ("丙", "b")],
                )

            async def fake_to_thread(func, *args, **kwargs):
                offloaded.append(func.__name__)
                return func(*args, **kwargs)

            offloaded: list[str] = []
            with (
                patch("app.sql.sql_routes.DB_MAPPING", {"query": str(db_path)}),
                patch("app.sql.choose_db.DB_MAPPING", {"query": str(db_path)}),
                patch("app.sql.sql_routes.asyncio.to_thread", side_effect=fake_to_thread),
            ):
                result = await query_table(
                    QueryParams(
                        db_key="query",
                        table_name="items",
                        page=1,
                        page_size=2,
                        filters={"category": ["a"]},
                    ),
                    user=_FakeUser(),
                    auth_db=None,
                )
                columns = await get_column_info("query", "items", user=_FakeUser(), auth_db=None)
                count = await get_table_count("query", "items", user=_FakeUser(), auth_db=None)

        self.assertEqual(result["total"], 2)
        self.assertEqual([row["name"] for row in result["data"]], ["甲", "乙"])
        self.assertEqual(count, {"count": 3})
        self.assertEqual([col["name"] for col in columns["columns"]], ["name", "category"])
        self.assertIn("_query_table_rows_sync", offloaded)
        self.assertIn("_query_table_count_sync", offloaded)
        self.assertIn("_get_column_info_sync", offloaded)
        self.assertIn("_get_table_count_sync", offloaded)


if __name__ == "__main__":
    unittest.main()
