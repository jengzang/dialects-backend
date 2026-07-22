"""
Compact database capability helpers for VillagesML.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing

from fastapi import HTTPException

from .schema_keys import C, T
from .schema_runtime import qcolumn, qtable, table_name


COMPACT_DETAIL = "This compact database does not include village-level detail tables."


def table_exists(conn: sqlite3.Connection, dbpath: str, logical_table: str) -> bool:
    """Return whether the mapped physical table exists in SQLite."""
    physical_name = table_name(dbpath, logical_table)
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ? LIMIT 1",
        (physical_name,),
    ).fetchone()
    return row is not None


def is_compact_db(conn: sqlite3.Connection, dbpath: str) -> bool:
    """Detect compact profile using explicit policy first, then table shape."""
    if table_exists(conn, dbpath, T.QUERY_POLICY_CONFIG):
        policy_table = qtable(dbpath, T.QUERY_POLICY_CONFIG)
        profile_col = qcolumn(dbpath, T.QUERY_POLICY_CONFIG, C.QUERY_POLICY_CONFIG.PROFILE)
        row = conn.execute(
            f"SELECT 1 FROM {policy_table} WHERE {profile_col} = 'compact' LIMIT 1"
        ).fetchone()
        if row is not None:
            return True

    has_villages = table_exists(conn, dbpath, T.VILLAGES)
    has_metadata = table_exists(conn, dbpath, T.METADATA_OVERVIEW_STATS) or table_exists(
        conn, dbpath, T.REGION_HIERARCHY_STATS
    )
    return not has_villages and has_metadata


def require_non_compact(conn: sqlite3.Connection, dbpath: str) -> None:
    """Raise a controlled API error for village-detail routes in compact DBs."""
    if is_compact_db(conn, dbpath):
        raise HTTPException(status_code=501, detail=COMPACT_DETAIL)


def require_non_compact_path(db_file: str, dbpath: str) -> None:
    """Open a short-lived connection and enforce non-compact mode."""
    with closing(sqlite3.connect(db_file)) as conn:
        require_non_compact(conn, dbpath)
