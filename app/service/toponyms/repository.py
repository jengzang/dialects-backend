from __future__ import annotations

from typing import Any

from app.service.toponyms.config import NATURAL_VILLAGE_PLACE_TYPE_CODE, TOPONYMS_DB_PATH
from app.sql.db_pool import get_db_pool


def _like_pattern(query: str, match_mode: str) -> str:
    if match_mode == "prefix":
        return f"{query}%"
    if match_mode == "suffix":
        return f"%{query}"
    if match_mode == "contains":
        return f"%{query}%"
    return query


def _name_condition(match_mode: str) -> str:
    if match_mode == "exact":
        return "standard_name = ?"
    return "standard_name LIKE ?"


def list_points_by_name(
    *,
    query: str,
    match_mode: str,
    limit: int,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    where_parts = [
        "place_type_code = ?",
        _name_condition(match_mode),
    ]
    params: list[Any] = [
        NATURAL_VILLAGE_PLACE_TYPE_CODE,
        _like_pattern(query, match_mode),
    ]

    if bbox is not None:
        min_lng, min_lat, max_lng, max_lat = bbox
        where_parts.extend(
            [
                "longitude BETWEEN ? AND ?",
                "latitude BETWEEN ? AND ?",
            ]
        )
        params.extend([min_lng, max_lng, min_lat, max_lat])

    row_limit = limit + 1 if limit > 0 else None
    limit_clause = ""
    if row_limit is not None:
        limit_clause = " LIMIT ?"
        params.append(row_limit)

    sql = """
        SELECT id, longitude, latitude
        FROM single
        WHERE {where_clause}
        ORDER BY id
        {limit_clause}
    """.format(where_clause=" AND ".join(where_parts), limit_clause=limit_clause)
    with pool.get_connection() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    selected_rows = rows[:limit] if limit > 0 else rows
    items = [
        {"id": row["id"], "longitude": row["longitude"], "latitude": row["latitude"]}
        for row in selected_rows
    ]
    return items, bool(limit > 0 and len(rows) > limit)


def sample_names(*, query: str, match_mode: str, limit: int) -> list[str]:
    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    params: list[Any] = [
        NATURAL_VILLAGE_PLACE_TYPE_CODE,
        _like_pattern(query, match_mode),
    ]
    limit_clause = ""
    if limit > 0:
        limit_clause = "LIMIT ?"
        params.append(limit)

    sql = """
        SELECT DISTINCT standard_name
        FROM single
        WHERE place_type_code = ?
          AND {name_condition}
          AND TRIM(COALESCE(standard_name, '')) <> ''
        ORDER BY standard_name
        {limit_clause}
    """.format(name_condition=_name_condition(match_mode), limit_clause=limit_clause)
    with pool.get_connection() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

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
