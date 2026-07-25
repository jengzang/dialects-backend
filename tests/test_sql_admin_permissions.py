import sqlite3
import tempfile
import unittest
from inspect import signature
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.service.auth.core.dependencies import get_current_user
from app.sql.sql_admin_routes import (
    batch_mutate_table,
    batch_replace_execute,
    get_my_sql_permissions,
    mutate_table,
)
from app.sql.sql_schemas import BatchReplaceExecuteParams, MutationParams


class _FakeUser:
    def __init__(self, user_id: int, role: str = "user"):
        self.id = user_id
        self.role = role


class _FakePermission:
    def __init__(self, can_write: bool, db_key: str = "query"):
        self.db_key = db_key
        self.can_write = can_write


class _FakeQuery:
    def __init__(self, permissions):
        self.permissions = permissions

    def filter(self, *args):
        return self

    def first(self):
        return self.permissions[0] if self.permissions else None

    def all(self):
        return self.permissions


class _FakeAuthDb:
    def __init__(self, can_write):
        if isinstance(can_write, list):
            self.permissions = can_write
        else:
            self.permissions = [] if can_write is None else [_FakePermission(can_write)]

    def query(self, model):
        return _FakeQuery(self.permissions)


class SqlAdminPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_my_sql_permissions_reports_admin_editable_databases(self) -> None:
        result = await get_my_sql_permissions(
            current_user=_FakeUser(user_id=1, role="admin"),
            auth_db=_FakeAuthDb(can_write=None),
        )

        self.assertEqual(result["role"], "admin")
        self.assertIn("query", result["editable_db_keys"])
        self.assertIn("query_admin", result["editable_db_keys"])
        self.assertNotIn("vocabulary", result["editable_db_keys"])
        self.assertNotIn("permissions", result)

    async def test_my_sql_permissions_only_reports_current_user_editable_databases(self) -> None:
        result = await get_my_sql_permissions(
            current_user=_FakeUser(user_id=7),
            auth_db=_FakeAuthDb(
                can_write=[
                    _FakePermission(db_key="query", can_write=True),
                    _FakePermission(db_key="dialects", can_write=False),
                    _FakePermission(db_key="unknown_internal", can_write=True),
                ]
            ),
        )

        self.assertEqual(result["role"], "user")
        self.assertEqual(result["editable_db_keys"], ["query"])
        self.assertNotIn("permissions", result)

    def test_write_endpoints_accept_current_user_before_db_permission_check(self) -> None:
        for endpoint in (mutate_table, batch_mutate_table, batch_replace_execute):
            dependency = signature(endpoint).parameters["current_user"].default.dependency
            self.assertIs(dependency, get_current_user)

    async def test_non_admin_with_db_write_permission_can_mutate_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "query.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE items (name TEXT)")

            with (
                patch("app.sql.sql_routes.DB_MAPPING", {"query": str(db_path)}),
                patch("app.sql.choose_db.DB_MAPPING", {"query": str(db_path)}),
                patch("app.service.auth.security.permission_cache.get_cached_permission_sync", return_value=None),
                patch("app.service.auth.security.permission_cache.set_cached_permission_sync"),
            ):
                result = await mutate_table(
                    MutationParams(
                        db_key="query",
                        table_name="items",
                        action="create",
                        data={"name": "甲"},
                    ),
                    current_user=_FakeUser(user_id=1),
                    auth_db=_FakeAuthDb(can_write=True),
                )

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute("SELECT name FROM items").fetchall()

        self.assertEqual(result["status"], "success")
        self.assertEqual(rows, [("甲",)])

    async def test_non_admin_without_db_write_permission_cannot_execute_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "query.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE items (name TEXT)")
                conn.execute("INSERT INTO items VALUES ('old')")

            with (
                patch("app.sql.sql_routes.DB_MAPPING", {"query": str(db_path)}),
                patch("app.sql.choose_db.DB_MAPPING", {"query": str(db_path)}),
                patch("app.service.auth.security.permission_cache.get_cached_permission_sync", return_value=None),
                patch("app.service.auth.security.permission_cache.set_cached_permission_sync"),
            ):
                with self.assertRaises(HTTPException) as raised:
                    await batch_replace_execute(
                        BatchReplaceExecuteParams(
                            db_key="query",
                            table_name="items",
                            columns=["name"],
                            find_text="old",
                            replace_text="new",
                            match_mode="exact",
                            is_empty_search=False,
                        ),
                        current_user=_FakeUser(user_id=1),
                        auth_db=_FakeAuthDb(can_write=False),
                    )

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute("SELECT name FROM items").fetchall()

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(rows, [("old",)])

    async def test_generic_sql_does_not_expose_vocabulary_database(self) -> None:
        from app.common.path import DB_MAPPING

        self.assertNotIn("vocabulary", DB_MAPPING)

        with self.assertRaises(HTTPException) as raised:
            await mutate_table(
                MutationParams(
                    db_key="vocabulary",
                    table_name="vocabulary_entries",
                    action="create",
                    data={
                        "location_name": "息烽",
                        "standard_word": "太阳",
                        "local_expression": "日头",
                        "ipa": "ipa",
                    },
                ),
                current_user=_FakeUser(user_id=1, role="admin"),
                auth_db=_FakeAuthDb(can_write=None),
            )

        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
