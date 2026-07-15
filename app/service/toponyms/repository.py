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
    place_type_code: str = NATURAL_VILLAGE_PLACE_TYPE_CODE,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    where_parts = [
        "place_type_code = ?",
        _name_condition(match_mode),
    ]
    params: list[Any] = [
        place_type_code,
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


def sample_names(
    *,
    query: str,
    match_mode: str,
    limit: int,
    place_type_code: str = NATURAL_VILLAGE_PLACE_TYPE_CODE,
) -> list[str]:
    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    params: list[Any] = [
        place_type_code,
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


def list_names_with_division_tree(
    *,
    query: str,
    match_mode: str,
    limit: int,
    place_type_code: str = NATURAL_VILLAGE_PLACE_TYPE_CODE,
) -> list[dict[str, Any]]:
    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    params: list[Any] = [
        place_type_code,
        _like_pattern(query, match_mode),
    ]
    limit_clause = ""
    if limit > 0:
        limit_clause = "LIMIT ?"
        params.append(limit)

    sql = """
        SELECT DISTINCT standard_name, area_code
        FROM single
        WHERE place_type_code = ?
          AND {name_condition}
          AND TRIM(COALESCE(standard_name, '')) <> ''
          AND TRIM(COALESCE(area_code, '')) <> ''
        ORDER BY area_code, standard_name
        {limit_clause}
    """.format(name_condition=_name_condition(match_mode), limit_clause=limit_clause)
    with pool.get_connection() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        division_rows = conn.execute(
            """
            SELECT code, name, parent_code, level
            FROM divisions
            ORDER BY level, code
            """
        ).fetchall()

    divisions = {
        row["code"]: {
            "code": row["code"],
            "name": row["name"],
            "parent_code": row["parent_code"],
            "level": row["level"],
        }
        for row in division_rows
    }

    root_nodes: dict[str, dict[str, Any]] = {}
    nodes_by_code: dict[str, dict[str, Any]] = {}

    for row in rows:
        path = _division_path(row["area_code"], divisions)
        if not path:
            continue

        parent_children = root_nodes
        for division in path:
            code = division["code"]
            if code not in parent_children:
                node = {
                    "_code": code,
                    "name": division["name"],
                    "level": division["level"],
                    "names": [],
                    "children": [],
                    "_children_by_code": {},
                }
                parent_children[code] = node
                nodes_by_code[code] = node
            node = parent_children[code]
            parent_children = node["_children_by_code"]

        leaf = nodes_by_code[path[-1]["code"]]
        if row["standard_name"] not in leaf["names"]:
            leaf["names"].append(row["standard_name"])

    return [_public_division_name_node(node) for node in root_nodes.values()]


def _division_path(
    area_code: str,
    divisions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    path: list[dict[str, Any]] = []
    current = divisions.get(area_code)
    while current is not None and current["level"] > 0:
        path.append(current)
        current = divisions.get(current["parent_code"])
    path.reverse()
    return path


def _public_division_name_node(node: dict[str, Any]) -> dict[str, Any]:
    children = [_public_division_name_node(child) for child in node["_children_by_code"].values()]
    return {
        "name": node["name"],
        "level": node["level"],
        "names": node["names"],
        "children": children,
    }


def list_details_by_ids(*, ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []

    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    placeholders = ",".join("?" for _ in ids)
    sql = """
        SELECT id, standard_name, place_type, place_type_code, area_code, longitude, latitude
        FROM single
        WHERE id IN ({placeholders})
    """.format(placeholders=placeholders)

    with pool.get_connection() as conn:
        rows = conn.execute(sql, tuple(ids)).fetchall()
        division_rows = conn.execute(
            """
            SELECT code, name, parent_code, level
            FROM divisions
            ORDER BY level, code
            """
        ).fetchall()

    rows_by_id = {row["id"]: row for row in rows}
    divisions = {
        row["code"]: {
            "code": row["code"],
            "name": row["name"],
            "parent_code": row["parent_code"],
            "level": row["level"],
        }
        for row in division_rows
    }

    items = []
    for requested_id in ids:
        row = rows_by_id.get(requested_id)
        if row is None:
            continue

        items.append(
            {
                "id": row["id"],
                "name": row["standard_name"],
                "place_type": row["place_type"],
                "place_type_code": row["place_type_code"],
                "longitude": row["longitude"],
                "latitude": row["latitude"],
                "division_path": [
                    {"name": division["name"], "level": division["level"]}
                    for division in _division_path(row["area_code"], divisions)
                ],
            }
        )

    return items


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
