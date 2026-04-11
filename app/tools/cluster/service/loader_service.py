"""
Cluster data loading and cache services.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter, defaultdict
from typing import Any, Dict, Optional, Sequence

from app.common.constants import get_table_schema, validate_table_name
from app.common.path import CHARACTERS_DB_PATH
from app.redis_client import sync_redis_client
from app.service.core.new_pho import generate_cache_key, process_chars_status
from app.sql.db_pool import get_db_pool
from app.tools.cluster.config import CACHE_TTL_SECONDS, FEATURE_COLUMN_MAP, TONE_SLOT_COLUMNS
from app.tools.cluster.utils import chunked, dedupe, parse_coordinates, quote_identifier, safe_text

logger = logging.getLogger(__name__)


def cache_get_json(key: str) -> Optional[Any]:
    try:
        cached = sync_redis_client.get(key)
        if cached:
            return json.loads(cached)
    except Exception as exc:
        logger.warning("cluster cache read failed: %s", exc)
    return None


def cache_set_json(key: str, value: Any, ttl: int = CACHE_TTL_SECONDS):
    try:
        sync_redis_client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
    except Exception as exc:
        logger.warning("cluster cache write failed: %s", exc)


def build_filters_cache_key(group: Dict[str, Any]) -> str:
    key_payload = {
        "table_name": group.get("table_name", "characters"),
        "filters": group.get("filters") or {},
        "exclude_columns": sorted(group.get("exclude_columns") or []),
    }
    encoded = json.dumps(
        key_payload, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    return "cluster:filters:" + hashlib.md5(encoded).hexdigest()


def resolve_preset_path_chars(
    group: Dict[str, Any],
    normalize_char_input,
) -> Dict[str, Any]:
    path_strings = group.get("path_strings") or []
    cache_key = generate_cache_key(
        path_strings=path_strings,
        column=group.get("column"),
        combine_query=bool(group.get("combine_query")),
        exclude_columns=group.get("exclude_columns"),
        table=group.get("table_name", "characters"),
    )

    cached_items = cache_get_json(cache_key)
    cache_hit = cached_items is not None
    if cached_items is None:
        cached_items = process_chars_status(
            path_strings=path_strings,
            column=group.get("column"),
            combine_query=bool(group.get("combine_query")),
            exclude_columns=group.get("exclude_columns"),
            table=group.get("table_name", "characters"),
        )
        cache_set_json(cache_key, cached_items)

    chars = []
    queries = []
    for item in cached_items or []:
        chars.extend(normalize_char_input(item.get("chars") or item.get("漢字") or item.get("汉字")))
        query_name = str(item.get("query") or "").strip()
        if query_name:
            queries.append(query_name)

    return {
        "chars": dedupe(chars),
        "query_labels": dedupe(queries),
        "cache_hit": cache_hit,
        "cache_key": cache_key,
        "resolver": "charlist_payload",
    }


def resolve_preset_filter_chars(
    group: Dict[str, Any],
    normalize_char_input,
) -> Dict[str, Any]:
    table_name = group.get("table_name", "characters")
    filters = group.get("filters") or {}

    if not validate_table_name(table_name):
        raise ValueError(f"Invalid table_name: {table_name}")

    schema = get_table_schema(table_name)
    valid_columns = set(schema["hierarchy"])
    invalid_columns = sorted(set(filters) - valid_columns)
    if invalid_columns:
        raise ValueError(
            f"Invalid filter columns for table '{table_name}': {', '.join(invalid_columns)}"
        )

    cache_key = build_filters_cache_key(group)
    cached = cache_get_json(cache_key)
    cache_hit = cached is not None
    if cached is not None:
        return {
            "chars": normalize_char_input(cached.get("chars")),
            "query_labels": [f"{table_name}:filters"],
            "cache_hit": cache_hit,
            "cache_key": cache_key,
            "resolver": "structured_filters",
        }

    conditions = []
    params = []
    for column, values in filters.items():
        uniq_values = dedupe(values)
        if not uniq_values:
            continue

        sub_conditions = []
        for value in uniq_values:
            if column == "等" and value == "三":
                sub_conditions.append(f"{quote_identifier(column)} IN (?, ?, ?, ?)")
                params.extend(["三A", "三B", "三C", "三銳"])
            else:
                sub_conditions.append(f"{quote_identifier(column)} = ?")
                params.append(value)
        conditions.append(f"({' OR '.join(sub_conditions)})")

    if not conditions:
        return {
            "chars": [],
            "query_labels": [f"{table_name}:filters"],
            "cache_hit": False,
            "cache_key": cache_key,
            "resolver": "structured_filters",
        }

    char_column = schema["char_column"]
    query = (
        f"SELECT DISTINCT {quote_identifier(char_column)} "
        f"FROM {quote_identifier(table_name)} "
        f"WHERE {' AND '.join(conditions)}"
    )

    for exclude_column in group.get("exclude_columns") or []:
        query += (
            f" AND ({quote_identifier(exclude_column)} != 1 "
            f"AND {quote_identifier(exclude_column)} != '1')"
        )

    pool = get_db_pool(CHARACTERS_DB_PATH)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        chars = [row[0] for row in cursor.fetchall() if row[0]]

    payload = {"chars": dedupe(chars)}
    cache_set_json(cache_key, payload)

    return {
        "chars": payload["chars"],
        "query_labels": [f"{table_name}:filters"],
        "cache_hit": cache_hit,
        "cache_key": cache_key,
        "resolver": "structured_filters",
    }


def load_location_details(
    locations: Sequence[str],
    db_path: str,
) -> Dict[str, Dict[str, Any]]:
    details: Dict[str, Dict[str, Any]] = {}
    if not locations:
        return details

    columns = [
        "簡稱",
        "省",
        "市",
        "縣",
        "鎮",
        "行政村",
        "自然村",
        "經緯度",
        "音典分區",
        "地圖集二分區",
        *TONE_SLOT_COLUMNS,
    ]
    quoted_columns = ", ".join(quote_identifier(column) for column in columns)

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        for batch in chunked(list(locations), 120):
            placeholders = ",".join("?" * len(batch))
            query = f"""
                SELECT {quoted_columns}
                FROM dialects
                WHERE 簡稱 IN ({placeholders})
            """
            cursor.execute(query, list(batch))
            for row in cursor.fetchall():
                row_map = dict(zip(columns, row))
                location = safe_text(row_map.get("簡稱"))
                if not location:
                    continue
                details[location] = {
                    "location": location,
                    "province": safe_text(row_map.get("省")),
                    "city": safe_text(row_map.get("市")),
                    "county": safe_text(row_map.get("縣")),
                    "town": safe_text(row_map.get("鎮")),
                    "administrative_village": safe_text(row_map.get("行政村")),
                    "natural_village": safe_text(row_map.get("自然村")),
                    "coordinates": parse_coordinates(row_map.get("經緯度")),
                    "yindian_region": safe_text(row_map.get("音典分區")),
                    "map_region": safe_text(row_map.get("地圖集二分區")),
                    "tone_classes": {
                        column: safe_text(row_map.get(column))
                        for column in TONE_SLOT_COLUMNS
                        if safe_text(row_map.get(column))
                    },
                }

    for location in locations:
        if location not in details:
            details[location] = {
                "location": location,
                "province": None,
                "city": None,
                "county": None,
                "town": None,
                "administrative_village": None,
                "natural_village": None,
                "coordinates": None,
                "yindian_region": None,
                "map_region": None,
                "tone_classes": {},
            }
    return details


def load_dialect_rows(
    locations: Sequence[str],
    chars: Sequence[str],
    db_path: str,
) -> Dict[str, Dict[str, Dict[str, set[str]]]]:
    data: Dict[str, Dict[str, Dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: {"initial": set(), "final": set(), "tone": set()})
    )
    if not locations or not chars:
        return data

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TEMP TABLE IF NOT EXISTS temp_cluster_locations(value TEXT PRIMARY KEY)"
        )
        cursor.execute(
            "CREATE TEMP TABLE IF NOT EXISTS temp_cluster_chars(value TEXT PRIMARY KEY)"
        )
        cursor.execute("DELETE FROM temp_cluster_locations")
        cursor.execute("DELETE FROM temp_cluster_chars")
        cursor.executemany(
            "INSERT OR IGNORE INTO temp_cluster_locations(value) VALUES (?)",
            ((str(location),) for location in locations),
        )
        cursor.executemany(
            "INSERT OR IGNORE INTO temp_cluster_chars(value) VALUES (?)",
            ((str(char),) for char in chars),
        )
        cursor.execute(
            """
            SELECT d.簡稱, d.漢字, d.聲母, d.韻母, d.聲調
            FROM dialects AS d
            INNER JOIN temp_cluster_locations AS l
                ON l.value = d.簡稱
            INNER JOIN temp_cluster_chars AS c
                ON c.value = d.漢字
            """
        )
        for row in cursor.fetchall():
            location = row[0]
            char = row[1]
            if row[2]:
                data[location][char]["initial"].add(str(row[2]).strip())
            if row[3]:
                data[location][char]["final"].add(str(row[3]).strip())
            if row[4]:
                data[location][char]["tone"].add(str(row[4]).strip())
    return data


def load_dimension_inventory_profiles(
    locations: Sequence[str],
    dimensions: Sequence[str],
    db_path: str,
) -> Dict[str, Dict[str, Dict[str, Dict[str, float]]]]:
    profiles: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {
        location: {} for location in locations
    }
    if not locations or not dimensions:
        return profiles

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        for dimension in sorted(set(dimensions)):
            column = FEATURE_COLUMN_MAP[dimension]
            per_location_counts: Dict[str, Counter[str]] = defaultdict(Counter)
            for batch in chunked(list(locations), 120):
                placeholders = ",".join("?" * len(batch))
                query = f"""
                    SELECT 簡稱, {quote_identifier(column)}, COUNT(DISTINCT 漢字)
                    FROM dialects
                    WHERE 簡稱 IN ({placeholders})
                      AND {quote_identifier(column)} IS NOT NULL
                      AND TRIM({quote_identifier(column)}) != ''
                    GROUP BY 簡稱, {quote_identifier(column)}
                """
                cursor.execute(query, list(batch))
                for location, raw_value, count in cursor.fetchall():
                    if not raw_value:
                        continue
                    per_location_counts[str(location)][str(raw_value).strip()] = int(count)

            for location in locations:
                counter = per_location_counts.get(location, Counter())
                total = float(sum(counter.values()))
                ordered_items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
                token_count = len(ordered_items)
                stats: Dict[str, Dict[str, float]] = {}
                for index, (token, count) in enumerate(ordered_items):
                    stats[token] = {
                        "share": (count / total) if total > 0 else 0.0,
                        "rank_pct": (
                            index / max(token_count - 1, 1)
                            if token_count > 1
                            else 0.0
                        ),
                        "count": float(count),
                    }
                profiles[location][dimension] = stats

    return profiles
