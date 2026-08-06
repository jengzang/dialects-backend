from __future__ import annotations

from typing import Any

from app.service.toponyms.config import (
    NATURAL_VILLAGE_PLACE_TYPE_CODE,
    TOPONYM_NAME_TREE_FULL_THRESHOLD as CONFIG_TOPONYM_NAME_TREE_FULL_THRESHOLD,
    TOPONYMS_DB_PATH,
)
from app.sql.db_pool import get_db_pool

TOPONYM_NAME_TREE_FULL_THRESHOLD = CONFIG_TOPONYM_NAME_TREE_FULL_THRESHOLD
TOPONYM_NAME_TREE_LEVELS = 4


def _like_pattern(query: str, match_mode: str) -> str:
    if match_mode == "prefix":
        return f"{query}%"
    if match_mode == "suffix":
        return f"%{query}"
    if match_mode == "contains":
        return f"%{query}%"
    return query


def _prefix_upper_bound(query: str) -> str:
    return f"{query[:-1]}{chr(ord(query[-1]) + 1)}"


def _name_condition(match_mode: str) -> str:
    if match_mode == "exact":
        return "standard_name = ?"
    if match_mode == "prefix":
        return "standard_name >= ? AND standard_name < ? AND standard_name LIKE ?"
    return "standard_name LIKE ?"


def _name_params(query: str, match_mode: str) -> list[str]:
    if match_mode == "prefix":
        return [query, _prefix_upper_bound(query), _like_pattern(query, match_mode)]
    return [_like_pattern(query, match_mode)]


def _base_name_filters(
    *,
    query: str,
    match_mode: str,
    place_type_code: str,
    bbox: tuple[float, float, float, float] | None = None,
    require_area_code: bool = False,
) -> tuple[list[str], list[Any]]:
    where_parts = [
        "place_type_code = ?",
        _name_condition(match_mode),
        "TRIM(COALESCE(standard_name, '')) <> ''",
    ]
    params: list[Any] = [
        place_type_code,
        *_name_params(query, match_mode),
    ]

    if require_area_code:
        where_parts.append("TRIM(COALESCE(area_code, '')) <> ''")

    if bbox is not None:
        min_lng, min_lat, max_lng, max_lat = bbox
        where_parts.extend(
            [
                "longitude BETWEEN ? AND ?",
                "latitude BETWEEN ? AND ?",
            ]
        )
        params.extend([min_lng, max_lng, min_lat, max_lat])

    return where_parts, params


def _add_area_code_filter(
    where_parts: list[str],
    params: list[Any],
    area_codes: list[str],
) -> None:
    if not area_codes:
        where_parts.append("1 = 0")
        return

    clauses = []
    for area_code in area_codes:
        clauses.append("area_code LIKE ?")
        params.append(f"{area_code}%")
    where_parts.append(f"({' OR '.join(clauses)})")


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
        *_name_params(query, match_mode),
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
    bbox: tuple[float, float, float, float] | None = None,
) -> list[str]:
    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    where_parts, params = _base_name_filters(
        query=query,
        match_mode=match_mode,
        place_type_code=place_type_code,
        bbox=bbox,
    )
    limit_clause = ""
    if limit > 0:
        limit_clause = "LIMIT ?"
        params.append(limit)

    sql = """
        SELECT DISTINCT standard_name
        FROM single
        WHERE {where_clause}
        ORDER BY standard_name
        {limit_clause}
    """.format(where_clause=" AND ".join(where_parts), limit_clause=limit_clause)
    with pool.get_connection() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    return [row["standard_name"] for row in rows]


def list_names_with_division_tree(
    *,
    query: str,
    match_mode: str,
    limit: int,
    place_type_code: str = NATURAL_VILLAGE_PLACE_TYPE_CODE,
    bbox: tuple[float, float, float, float] | None = None,
    parent_path: list[str] | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    del limit
    pool = get_db_pool(TOPONYMS_DB_PATH, pool_size=4)
    with pool.get_connection() as conn:
        divisions = _load_divisions(conn)
        if parent_path:
            return _list_lazy_tree_node(
                conn=conn,
                divisions=divisions,
                query=query,
                match_mode=match_mode,
                place_type_code=place_type_code,
                bbox=bbox,
                parent_path=parent_path,
                page=page,
                page_size=page_size,
            )

        filtered_count = _count_distinct_name_area(
            conn=conn,
            query=query,
            match_mode=match_mode,
            place_type_code=place_type_code,
            bbox=bbox,
        )
        if filtered_count > TOPONYM_NAME_TREE_FULL_THRESHOLD:
            return {
                "mode": "lazy_fallback",
                "reason": "tree_result_too_large",
                "threshold": TOPONYM_NAME_TREE_FULL_THRESHOLD,
                "filtered_count": filtered_count,
                "levels": TOPONYM_NAME_TREE_LEVELS,
                "lazy_bootstrap": _build_lazy_bootstrap(
                    conn=conn,
                    divisions=divisions,
                    query=query,
                    match_mode=match_mode,
                    place_type_code=place_type_code,
                    bbox=bbox,
                ),
            }

        rows = _fetch_distinct_name_area_rows(
            conn=conn,
            query=query,
            match_mode=match_mode,
            place_type_code=place_type_code,
            bbox=bbox,
            limit=0,
        )

    return {
        "mode": "full",
        "items": _build_public_name_tree(rows, divisions),
        "levels": TOPONYM_NAME_TREE_LEVELS,
    }


def _load_divisions(conn) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT code, name, parent_code, level
        FROM divisions
        ORDER BY level, code
        """
    ).fetchall()
    return {
        row["code"]: {
            "code": row["code"],
            "name": row["name"],
            "parent_code": row["parent_code"],
            "level": row["level"],
        }
        for row in rows
    }


def _count_distinct_name_area(
    *,
    conn,
    query: str,
    match_mode: str,
    place_type_code: str,
    bbox: tuple[float, float, float, float] | None,
    area_codes: list[str] | None = None,
) -> int:
    where_parts, params = _base_name_filters(
        query=query,
        match_mode=match_mode,
        place_type_code=place_type_code,
        bbox=bbox,
        require_area_code=True,
    )
    if area_codes is not None:
        _add_area_code_filter(where_parts, params, area_codes)
    sql = """
        SELECT COUNT(*) AS count
        FROM (
            SELECT DISTINCT standard_name, area_code
            FROM single
            WHERE {where_clause}
        )
    """.format(where_clause=" AND ".join(where_parts))
    row = conn.execute(sql, tuple(params)).fetchone()
    return int(row["count"]) if row else 0


def _fetch_distinct_name_area_rows(
    *,
    conn,
    query: str,
    match_mode: str,
    place_type_code: str,
    bbox: tuple[float, float, float, float] | None,
    limit: int = 0,
    area_codes: list[str] | None = None,
    offset: int = 0,
    row_limit: int | None = None,
) -> list[Any]:
    where_parts, params = _base_name_filters(
        query=query,
        match_mode=match_mode,
        place_type_code=place_type_code,
        bbox=bbox,
        require_area_code=True,
    )
    if area_codes is not None:
        _add_area_code_filter(where_parts, params, area_codes)

    sql = """
        SELECT DISTINCT standard_name, area_code
        FROM single
        WHERE {where_clause}
        ORDER BY area_code, standard_name
    """.format(where_clause=" AND ".join(where_parts))
    actual_limit = row_limit if row_limit is not None else limit
    if actual_limit > 0:
        sql += " LIMIT ? OFFSET ?"
        params.extend([actual_limit, offset])
    return conn.execute(sql, tuple(params)).fetchall()


def _build_public_name_tree(rows: list[Any], divisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
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


def _build_lazy_bootstrap(
    *,
    conn,
    divisions: dict[str, dict[str, Any]],
    query: str,
    match_mode: str,
    place_type_code: str,
    bbox: tuple[float, float, float, float] | None,
) -> list[dict[str, Any]]:
    rows = _fetch_distinct_area_rows(
        conn=conn,
        query=query,
        match_mode=match_mode,
        place_type_code=place_type_code,
        bbox=bbox,
    )
    roots: dict[str, dict[str, Any]] = {}
    seen_children: dict[str, set[str]] = {}
    for row in rows:
        path = _division_path(row["area_code"], divisions)
        if not path:
            continue
        root = path[0]
        if root["code"] not in roots:
            roots[root["code"]] = {"name": root["name"], "level": root["level"], "children": []}
            seen_children[root["code"]] = set()
        if len(path) < 2:
            continue
        child = path[1]
        if child["code"] not in seen_children[root["code"]]:
            roots[root["code"]]["children"].append({"name": child["name"], "level": child["level"]})
            seen_children[root["code"]].add(child["code"])
    return list(roots.values())


def _fetch_distinct_area_rows(
    *,
    conn,
    query: str,
    match_mode: str,
    place_type_code: str,
    bbox: tuple[float, float, float, float] | None,
    area_codes: list[str] | None = None,
) -> list[Any]:
    where_parts, params = _base_name_filters(
        query=query,
        match_mode=match_mode,
        place_type_code=place_type_code,
        bbox=bbox,
        require_area_code=True,
    )
    if area_codes is not None:
        _add_area_code_filter(where_parts, params, area_codes)
    sql = """
        SELECT DISTINCT area_code
        FROM single
        WHERE {where_clause}
        ORDER BY area_code
    """.format(where_clause=" AND ".join(where_parts))
    return conn.execute(sql, tuple(params)).fetchall()


def _list_lazy_tree_node(
    *,
    conn,
    divisions: dict[str, dict[str, Any]],
    query: str,
    match_mode: str,
    place_type_code: str,
    bbox: tuple[float, float, float, float] | None,
    parent_path: list[str],
    page: int,
    page_size: int,
) -> dict[str, Any]:
    parent_codes = _resolve_parent_codes(parent_path, divisions)
    if len(parent_path) >= TOPONYM_NAME_TREE_LEVELS:
        offset = (page - 1) * page_size
        rows = _fetch_distinct_name_area_rows(
            conn=conn,
            query=query,
            match_mode=match_mode,
            place_type_code=place_type_code,
            bbox=bbox,
            area_codes=parent_codes,
            offset=offset,
            row_limit=page_size + 1,
        )
        names = [row["standard_name"] for row in rows[:page_size]]
        return {
            "mode": "lazy",
            "level": TOPONYM_NAME_TREE_LEVELS,
            "parent_path": parent_path,
            "names": names,
            "page": page,
            "page_size": page_size,
            "has_more": len(rows) > page_size,
        }

    child_level = len(parent_path) + 1
    area_rows = _fetch_distinct_area_rows(
        conn=conn,
        query=query,
        match_mode=match_mode,
        place_type_code=place_type_code,
        bbox=bbox,
        area_codes=parent_codes,
    )
    children_by_code: dict[str, dict[str, Any]] = {}
    for row in area_rows:
        path = _division_path(row["area_code"], divisions)
        if len(path) < child_level:
            continue
        if [division["name"] for division in path[: len(parent_path)]] != parent_path:
            continue
        child = path[child_level - 1]
        children_by_code[child["code"]] = {"name": child["name"], "level": child["level"]}

    return {
        "mode": "lazy",
        "level": child_level,
        "parent_path": parent_path,
        "children": list(children_by_code.values()),
        "has_more": False,
    }


def _resolve_parent_codes(
    parent_path: list[str],
    divisions: dict[str, dict[str, Any]],
) -> list[str]:
    if not parent_path:
        return []

    codes = []
    for division in divisions.values():
        if division["level"] != len(parent_path):
            continue
        path = _division_path(division["code"], divisions)
        if [item["name"] for item in path] == parent_path:
            codes.append(division["code"])
    return codes


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
        division_paths_by_area_code = {
            row["area_code"]: _division_path_from_db(conn, row["area_code"])
            for row in rows
            if row["area_code"]
        }

    rows_by_id = {row["id"]: row for row in rows}

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
                    for division in division_paths_by_area_code.get(row["area_code"], [])
                ],
            }
        )

    return items


def _division_path_from_db(conn, area_code: str) -> list[dict[str, Any]]:
    path: list[dict[str, Any]] = []
    current_code = area_code
    while current_code:
        row = conn.execute(
            """
            SELECT code, name, parent_code, level
            FROM divisions
            WHERE code = ?
            """,
            (current_code,),
        ).fetchone()
        if row is None or row["level"] <= 0:
            break
        path.append(
            {
                "code": row["code"],
                "name": row["name"],
                "parent_code": row["parent_code"],
                "level": row["level"],
            }
        )
        current_code = row["parent_code"]

    path.reverse()
    return path


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
