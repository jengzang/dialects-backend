from __future__ import annotations

from typing import Any

from app.service.toponyms.config import (
    NATURAL_VILLAGE_PLACE_TYPE_CODES,
    QUERY_TIMEOUT_SECONDS,
    TOPONYM_NAME_TREE_FULL_THRESHOLD as CONFIG_TOPONYM_NAME_TREE_FULL_THRESHOLD,
    TOPONYMS_DB_PATH,
)
from app.service.toponyms.resources import connection, check_deadline, QueryTooBroad
from app.service.toponyms.divisions import (
    load_paths, division_path as _division_path, resolve_parent_codes,
)

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


def _in_clause(values: list[str]) -> str:
    return f"({','.join('?' for _ in values)})"


def _base_name_filters(
    *,
    query: str,
    match_mode: str,
    place_type_codes: list[str],
    bbox: tuple[float, float, float, float] | None = None,
    require_area_code: bool = False,
) -> tuple[list[str], list[Any]]:
    where_parts = [
        f"place_type_code IN {_in_clause(place_type_codes)}",
        _name_condition(match_mode),
        "TRIM(COALESCE(standard_name, '')) <> ''",
    ]
    params: list[Any] = [
        *place_type_codes,
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


def _add_area_scope_filter(
    where_parts: list[str],
    params: list[Any],
    area_code: str | None,
    area_scope: str,
) -> None:
    if area_code is None:
        return
    if area_scope == "exact":
        where_parts.append("area_code = ?")
        params.append(area_code)
        return
    where_parts.append("area_code LIKE ?")
    params.append(f"{area_code}%")


def points_query(
    conn, *,
    query: str,
    match_mode: str,
    limit: int,
    place_type_codes: list[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[str, list[Any]]:
    if place_type_codes is None:
        place_type_codes = NATURAL_VILLAGE_PLACE_TYPE_CODES
    where_parts = [
        f"place_type_code IN {_in_clause(place_type_codes)}",
        _name_condition(match_mode),
    ]
    params: list[Any] = [
        *place_type_codes,
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
    # With no bbox, matching names in the covering index avoids a table
    # lookup for every rejected candidate. Missing indexes remain supported.
    if bbox is None and match_mode in {"contains", "suffix"}:
        has_index = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_single_type_name_id'"
        ).fetchone()
        if has_index:
            sql = """
                SELECT id, longitude, latitude FROM single
                WHERE id IN (
                    SELECT id FROM single INDEXED BY idx_single_type_name_id
                    WHERE {where_clause} ORDER BY id {limit_clause}
                ) ORDER BY id
            """.format(where_clause=" AND ".join(where_parts), limit_clause=limit_clause)
    return sql, params



def list_points_by_name(
    *,
    query: str,
    match_mode: str,
    limit: int,
    place_type_codes: list[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    with connection(TOPONYMS_DB_PATH, timeout=None if limit == 0 else QUERY_TIMEOUT_SECONDS) as conn:
        sql, params = points_query(conn, query=query, match_mode=match_mode, limit=limit,
                                   place_type_codes=place_type_codes, bbox=bbox)
        rows = conn.execute(sql, params).fetchall()
    selected_rows = rows[:limit] if limit > 0 else rows
    items = [
        {"id": row["id"], "longitude": row["longitude"], "latitude": row["latitude"]}
        for row in selected_rows
    ]
    return items, bool(limit > 0 and len(rows) > limit)


def search_query(
    *,
    query: str,
    match_mode: str,
    limit: int,
    place_type_codes: list[str] | None = None,
    area_code: str | None = None,
    area_scope: str = "descendants",
    bbox: tuple[float, float, float, float] | None = None,
    include_area_code: bool = False,
    include_place_type_code: bool = False,
) -> tuple[str, list[Any]]:
    if place_type_codes is None:
        place_type_codes = NATURAL_VILLAGE_PLACE_TYPE_CODES

    single_where_parts = [
        f"place_type_code IN {_in_clause(place_type_codes)}",
        _name_condition(match_mode),
        "TRIM(COALESCE(standard_name, '')) <> ''",
    ]
    single_params: list[Any] = [
        *place_type_codes,
        *_name_params(query, match_mode),
    ]
    _add_area_scope_filter(single_where_parts, single_params, area_code, area_scope)
    if bbox is not None:
        min_lng, min_lat, max_lng, max_lat = bbox
        single_where_parts.extend(
            [
                "longitude BETWEEN ? AND ?",
                "latitude BETWEEN ? AND ?",
            ]
        )
        single_params.extend([min_lng, max_lng, min_lat, max_lat])

    selects = [
        """
        SELECT id, standard_name AS name, {area_projection} AS area_code, place_type_code
        FROM single
        WHERE {where_clause}
        """.format(where_clause=" AND ".join(single_where_parts),
                   area_projection="area_code" if include_area_code else "NULL")
    ]
    params = [*single_params]

    if bbox is None:
        multi_where_parts = [
            f"place_type_code IN {_in_clause(place_type_codes)}",
            _name_condition(match_mode),
            "TRIM(COALESCE(standard_name, '')) <> ''",
        ]
        multi_params: list[Any] = [
            *place_type_codes,
            *_name_params(query, match_mode),
        ]
        _add_area_scope_filter(multi_where_parts, multi_params, area_code, area_scope)
        selects.append(
            """
            SELECT id, standard_name AS name, {area_projection} AS area_code, place_type_code
            FROM multi
            WHERE {where_clause}
            """.format(where_clause=" AND ".join(multi_where_parts),
                       area_projection="area_code" if include_area_code else "NULL")
        )
        params.extend(multi_params)

    row_limit = limit + 1 if limit > 0 else None
    limit_clause = ""
    if row_limit is not None:
        limit_clause = " LIMIT ?"
        params.append(row_limit)

    sql = """
        SELECT id, name, area_code, place_type_code
        FROM (
            {union_sql}
        )
        ORDER BY name, id
        {limit_clause}
    """.format(union_sql=" UNION ALL ".join(selects), limit_clause=limit_clause)

    return sql, params


def search_toponyms(
    *,
    query: str,
    match_mode: str,
    limit: int,
    place_type_codes: list[str] | None = None,
    area_code: str | None = None,
    area_scope: str = "descendants",
    bbox: tuple[float, float, float, float] | None = None,
    include_area_code: bool = False,
    include_place_type_code: bool = False,
) -> tuple[list[dict[str, Any]], bool]:
    sql, params = search_query(query=query, match_mode=match_mode, limit=limit,
                               place_type_codes=place_type_codes, area_code=area_code,
                               area_scope=area_scope, bbox=bbox,
                               include_area_code=include_area_code,
                               include_place_type_code=include_place_type_code)
    with connection(TOPONYMS_DB_PATH, timeout=None if limit == 0 else QUERY_TIMEOUT_SECONDS) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    selected_rows = rows[:limit] if limit > 0 else rows
    items = []
    for row in selected_rows:
        item = {"id": row["id"], "name": row["name"]}
        if include_area_code:
            item["area_code"] = row["area_code"]
        if include_place_type_code:
            item["place_type_code"] = row["place_type_code"]
        items.append(item)

    return items, bool(limit > 0 and len(rows) > limit)


def names_query(
    *,
    query: str,
    match_mode: str,
    limit: int,
    place_type_codes: list[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> tuple[str, list[Any]]:
    if place_type_codes is None:
        place_type_codes = NATURAL_VILLAGE_PLACE_TYPE_CODES
    where_parts, params = _base_name_filters(
        query=query,
        match_mode=match_mode,
        place_type_codes=place_type_codes,
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
    return sql, params


def sample_names(
    *,
    query: str,
    match_mode: str,
    limit: int,
    place_type_codes: list[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[str]:
    sql, params = names_query(query=query, match_mode=match_mode, limit=limit,
                              place_type_codes=place_type_codes, bbox=bbox)
    with connection(TOPONYMS_DB_PATH, timeout=None if limit == 0 else QUERY_TIMEOUT_SECONDS) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    return [row["standard_name"] for row in rows]


def list_names_with_division_tree(
    *,
    query: str,
    match_mode: str,
    limit: int,
    place_type_codes: list[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    parent_path: list[str] | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    if place_type_codes is None:
        place_type_codes = NATURAL_VILLAGE_PLACE_TYPE_CODES
    with connection(TOPONYMS_DB_PATH, timeout=None if limit == 0 else QUERY_TIMEOUT_SECONDS) as conn:
        if parent_path:
            return _list_lazy_tree_node(
                conn=conn, query=query, match_mode=match_mode,
                place_type_codes=place_type_codes, bbox=bbox,
                parent_path=parent_path, page=page, page_size=page_size,
            )
        rows = _fetch_distinct_name_area_rows(
            conn=conn, query=query, match_mode=match_mode,
            place_type_codes=place_type_codes, bbox=bbox,
            row_limit=TOPONYM_NAME_TREE_FULL_THRESHOLD + 1, probe=True,
        )
        if len(rows) > TOPONYM_NAME_TREE_FULL_THRESHOLD:
            return {
                "mode": "lazy_fallback", "reason": "tree_result_too_large",
                "threshold": TOPONYM_NAME_TREE_FULL_THRESHOLD,
                "filtered_count": None, "count_exact": False,
                "count_lower_bound": TOPONYM_NAME_TREE_FULL_THRESHOLD + 1,
                "levels": TOPONYM_NAME_TREE_LEVELS,
                "lazy_bootstrap": _build_lazy_bootstrap(
                    conn=conn, query=query, match_mode=match_mode,
                    place_type_codes=place_type_codes, bbox=bbox,
                ),
            }
        rows.sort(key=lambda row: (row["area_code"], row["standard_name"]))
        divisions = load_paths(conn, {row["area_code"] for row in rows})
        return {
            "mode": "full", "items": _build_public_name_tree(rows, divisions),
            "levels": TOPONYM_NAME_TREE_LEVELS,
        }


def _fetch_distinct_name_area_rows(
    *,
    conn,
    query: str,
    match_mode: str,
    place_type_codes: list[str],
    bbox: tuple[float, float, float, float] | None,
    limit: int = 0,
    area_codes: list[str] | None = None,
    offset: int = 0,
    row_limit: int | None = None,
    probe: bool = False,
) -> list[Any]:
    where_parts, params = _base_name_filters(
        query=query,
        match_mode=match_mode,
        place_type_codes=place_type_codes,
        bbox=bbox,
        require_area_code=True,
    )
    if area_codes is not None:
        _add_area_code_filter(where_parts, params, area_codes)

    sql = """
        SELECT DISTINCT standard_name, area_code
        FROM single
        WHERE {where_clause}
    """.format(where_clause=" AND ".join(where_parts))
    if not probe:
        sql += " ORDER BY area_code, standard_name"
    actual_limit = row_limit if row_limit is not None else limit
    if actual_limit > 0:
        sql += " LIMIT ? OFFSET ?"
        params.extend([actual_limit, offset])
    return conn.execute(sql, tuple(params)).fetchall()


def _build_public_name_tree(rows: list[Any], divisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    root_nodes: dict[str, dict[str, Any]] = {}
    nodes_by_code: dict[str, dict[str, Any]] = {}

    for row in rows:
        check_deadline()
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
    query: str,
    match_mode: str,
    place_type_codes: list[str],
    bbox: tuple[float, float, float, float] | None,
) -> list[dict[str, Any]]:
    paths = _iter_area_paths(
        conn=conn,
        query=query,
        match_mode=match_mode,
        place_type_codes=place_type_codes,
        bbox=bbox,
    )
    roots: dict[str, dict[str, Any]] = {}
    seen_children: dict[str, set[str]] = {}
    for path in paths:
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


def _iter_area_paths(
    *,
    conn,
    query: str,
    match_mode: str,
    place_type_codes: list[str],
    bbox: tuple[float, float, float, float] | None,
    area_codes: list[str] | None = None,
) -> list[Any]:
    where_parts, params = _base_name_filters(
        query=query,
        match_mode=match_mode,
        place_type_codes=place_type_codes,
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
    cursor = conn.execute(sql, tuple(params))
    while True:
        check_deadline()
        rows = cursor.fetchmany(256)
        if not rows:
            break
        divisions = load_paths(conn, {row["area_code"] for row in rows})
        for row in rows:
            yield _division_path(row["area_code"], divisions)



def _list_lazy_tree_node(
    *,
    conn,
    query: str,
    match_mode: str,
    place_type_codes: list[str],
    bbox: tuple[float, float, float, float] | None,
    parent_path: list[str],
    page: int,
    page_size: int,
) -> dict[str, Any]:
    parent_codes = resolve_parent_codes(conn, parent_path)
    divisions = load_paths(conn, parent_codes)
    parent_divisions = [divisions[code] for code in parent_codes if code in divisions]
    if (
        parent_divisions
        and all(division["level"] >= TOPONYM_NAME_TREE_LEVELS for division in parent_divisions)
    ) or (not parent_divisions and len(parent_path) >= TOPONYM_NAME_TREE_LEVELS):
        offset = (page - 1) * page_size
        rows = _fetch_distinct_name_area_rows(
            conn=conn,
            query=query,
            match_mode=match_mode,
            place_type_codes=place_type_codes,
            bbox=bbox,
            area_codes=parent_codes,
            offset=offset,
            row_limit=page_size + 1,
        )
        names = [row["standard_name"] for row in rows[:page_size]]
        return {
            "mode": "lazy",
            "level": max((division["level"] for division in parent_divisions), default=TOPONYM_NAME_TREE_LEVELS),
            "parent_path": parent_path,
            "names": names,
            "page": page,
            "page_size": page_size,
            "has_more": len(rows) > page_size,
        }

    paths = _iter_area_paths(
        conn=conn,
        query=query,
        match_mode=match_mode,
        place_type_codes=place_type_codes,
        bbox=bbox,
        area_codes=parent_codes,
    )
    children_by_code: dict[str, dict[str, Any]] = {}
    for path in paths:
        child_index = len(parent_path)
        if len(path) <= child_index:
            continue
        if [division["name"] for division in path[: len(parent_path)]] != parent_path:
            continue
        child = path[child_index]
        children_by_code[child["code"]] = {"name": child["name"], "level": child["level"]}

    child_level = max((child["level"] for child in children_by_code.values()), default=len(parent_path) + 1)
    return {
        "mode": "lazy",
        "level": child_level,
        "parent_path": parent_path,
        "children": list(children_by_code.values()),
        "has_more": False,
    }


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

    placeholders = ",".join("?" for _ in ids)
    single_sql = """
        SELECT id, standard_name, place_type, place_type_code, area_code, longitude, latitude
        FROM single
        WHERE id IN ({placeholders})
    """.format(placeholders=placeholders)
    multi_sql = """
        SELECT id, standard_name, place_type, place_type_code, area_code,
               NULL AS longitude, NULL AS latitude
        FROM multi
        WHERE id IN ({placeholders})
    """.format(placeholders=placeholders)

    with connection(TOPONYMS_DB_PATH) as conn:
        rows = [
            *conn.execute(single_sql, tuple(ids)).fetchall(),
            *conn.execute(multi_sql, tuple(ids)).fetchall(),
        ]
        codes = {row["area_code"] for row in rows if row["area_code"]}
        divisions = load_paths(conn, codes)
        division_paths_by_area_code = {
            code: _division_path(code, divisions) for code in codes
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


def list_child_divisions(*, parent_code: str) -> list[dict[str, Any]]:
    sql = """
        SELECT code, name, level, COALESCE(single_cnt, 0) AS single_count
        FROM divisions
        WHERE parent_code = ?
        ORDER BY code
    """
    with connection(TOPONYMS_DB_PATH) as conn:
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
