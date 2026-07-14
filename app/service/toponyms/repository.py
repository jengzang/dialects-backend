from __future__ import annotations

from typing import Any

from app.service.toponyms.config import NATURAL_VILLAGE_PLACE_TYPE_CODE, TOPONYMS_DB_PATH
from app.sql.db_pool import get_db_pool


def list_all_points() -> list[dict[str, Any]]:
    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    sql = """
        SELECT id, longitude, latitude
        FROM single
        WHERE place_type_code = ?
        ORDER BY id
    """
    with pool.get_connection() as conn:
        rows = conn.execute(sql, (NATURAL_VILLAGE_PLACE_TYPE_CODE,)).fetchall()

    items = [
        {"id": row["id"], "longitude": row["longitude"], "latitude": row["latitude"]}
        for row in rows
    ]
    return items


def sample_names(*, query: str, limit: int) -> list[str]:
    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    sql = """
        SELECT DISTINCT standard_name
        FROM single
        WHERE place_type_code = ?
          AND standard_name LIKE ?
          AND TRIM(COALESCE(standard_name, '')) <> ''
        ORDER BY standard_name
        LIMIT ?
    """
    with pool.get_connection() as conn:
        rows = conn.execute(
            sql,
            (
                NATURAL_VILLAGE_PLACE_TYPE_CODE,
                f"{query}%",
                limit,
            ),
        ).fetchall()

    return [row["standard_name"] for row in rows]


def list_child_divisions(*, parent_code: str) -> list[dict[str, Any]]:
    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    sql = """
        SELECT code, name, level, COALESCE(single_cnt, 0) AS single_count
        FROM divisions
        WHERE parent_code = ?
        ORDER BY code
    """
    with pool.get_connection() as conn:
        rows = conn.execute(sql, (parent_code,)).fetchall()

    return [
        {
            "code": row["code"],
            "name": row["name"],
            "level": row["level"],
            "single_count": row["single_count"],
        }
        for row in rows
    ]
