"""
Runtime helpers for VillagesML schema mappings.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from app.common.path import DB_MAPPING

from . import schema_config


_IDENTIFIER_RE = re.compile(r"^[\w\u4e00-\u9fff]+$", re.UNICODE)
_DEFAULT_LOGICAL_ALIASES = {
    "villages": {
        "rowid": "ROWID",
        "village_id": "village_id",
        "name": "自然村_规范名",
        "raw_name": "自然村",
        "committee": "村委会",
        "city": "市级",
        "county": "区县级",
        "township": "乡镇级",
        "longitude": "longitude",
        "latitude": "latitude",
    },
    "villages_raw": {
        "name": "自然村",
        "committee": "村委会",
        "city": "市级",
        "county": "区县级",
        "township": "乡镇级",
        "longitude": "longitude",
        "latitude": "latitude",
    },
}


def quote_identifier(identifier: str) -> str:
    """Quote a SQLite identifier after rejecting unsafe characters."""
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("SQLite identifier must be a non-empty string")
    if identifier.upper() == "ROWID":
        return "ROWID"
    if not _IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Unsafe SQLite identifier: {identifier!r}")
    return '"' + identifier.replace('"', '""') + '"'


def get_database_config(dbpath: str | None = None) -> dict[str, Any]:
    """Return the VillagesML database config for a public mapping key."""
    db_key = dbpath or schema_config.DEFAULT_DATABASE_KEY
    config = schema_config.VILLAGES_DATABASES.get(db_key)
    if config is None:
        available = ", ".join(sorted(schema_config.VILLAGES_DATABASES))
        raise ValueError(f"Unknown villagesML database key: {db_key}. Available keys: {available}")
    return config


def resolve_db_path(dbpath: str | None = None) -> str:
    """Resolve a public VillagesML database key to a configured local path."""
    config = get_database_config(dbpath)
    path_key = config.get("path_key")
    if path_key not in DB_MAPPING:
        raise ValueError(f"VillagesML database path key is not configured: {path_key}")
    return DB_MAPPING[path_key]


def table_config(dbpath: str | None, logical_table: str) -> dict[str, Any]:
    """Return a logical table config for a database key."""
    tables = get_database_config(dbpath).get("tables", {})
    config = tables.get(logical_table)
    if config is None:
        raise ValueError(f"Unknown VillagesML logical table: {logical_table}")
    return config


def table_name(dbpath: str | None, logical_table: str) -> str:
    return table_config(dbpath, logical_table)["name"]


def qtable(dbpath: str | None, logical_table: str) -> str:
    """Return a safely quoted physical table name."""
    return quote_identifier(table_name(dbpath, logical_table))


def column_name(dbpath: str | None, logical_table: str, logical_column: str) -> str:
    columns = table_config(dbpath, logical_table).get("columns", {})
    column = columns.get(logical_column)
    if column is None:
        raise ValueError(
            f"Unknown VillagesML logical column: {logical_table}.{logical_column}"
        )
    return column


def qcolumn(dbpath: str | None, logical_table: str, logical_column: str) -> str:
    """Return a safely quoted physical column name."""
    return quote_identifier(column_name(dbpath, logical_table, logical_column))


def run_id_analysis_type(dbpath: str | None, logical_table: str) -> str:
    """Return the active-run analysis type configured for a logical table."""
    run_id_config = table_config(dbpath, logical_table).get("run_id", {})
    analysis_type = run_id_config.get("analysis_type")
    if not analysis_type:
        raise ValueError(f"Logical table does not configure a run_id analysis type: {logical_table}")
    return analysis_type


def column_value_map(dbpath: str | None, logical_table: str, logical_column: str) -> dict[str, str]:
    """Return a value-level mapping for a column, or empty dict if none configured.

    Used when the same logical API value maps to different physical values across tables.
    """
    value_maps = table_config(dbpath, logical_table).get("column_value_maps", {})
    return value_maps.get(logical_column, {})


_REGION_LEVEL_MAP: dict[str, str] = {"市级": "city", "区县级": "county", "乡镇级": "township"}


def normalize_region_level(dbpath: str | None, logical_table: str, region_level: str) -> str:
    """Normalize region_level input (Chinese or English) to the physical DB value.

    Falls back to per-table column_value_map, then a shared Chinese→English map,
    then passes through the input unchanged.
    """
    table_map = column_value_map(dbpath, logical_table, "region_level")
    if table_map:
        return table_map.get(region_level, region_level)
    return _REGION_LEVEL_MAP.get(region_level, region_level)


def install_schema_views(conn: sqlite3.Connection, dbpath: str | None = None) -> None:
    """Install temp views that expose configured physical tables as logical names."""
    config = get_database_config(dbpath)
    for logical_table, physical in config.get("tables", {}).items():
        logical_columns = physical.get("logical_columns") or _DEFAULT_LOGICAL_ALIASES.get(logical_table)

        logical_name = physical.get("logical_name", logical_table)
        physical_name = physical.get("name")
        columns = physical.get("columns", {})
        if not logical_name or not physical_name:
            continue
        if logical_name == physical_name:
            continue
        conn.execute(f"DROP VIEW IF EXISTS temp.{quote_identifier(logical_name)}")

        select_parts = []
        if logical_columns:
            for logical_key, logical_alias in logical_columns.items():
                source_column = columns.get(logical_key)
                if source_column is None:
                    continue
                select_parts.append(
                    f"{quote_identifier(source_column)} AS {quote_identifier(logical_alias)}"
                )
        else:
            select_parts.append("*")

        if not select_parts:
            continue

        conn.execute(
            f"""
            CREATE TEMP VIEW {quote_identifier(logical_name)} AS
            SELECT {", ".join(select_parts)}
            FROM {quote_identifier(physical_name)}
            """
        )
