"""
cluster 数据加载层。

这一层承担三类职责：
1. 把 group 的字集来源真正解析成字符列表；
2. 从 `dialects` / `characters` 等表中批量读取聚类所需数据；
3. 对部分可复用的中间结果做缓存，降低重复请求开销。
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter, defaultdict
from typing import Any, Dict, Optional, Sequence

from app.common.constants import get_table_schema, validate_table_name
from app.common.path import CHARACTERS_DB_PATH
from app.service.core.new_pho import generate_cache_key, process_chars_status
from app.tools.cluster.service.cache_service import (
    get_cluster_cache_sync,
    set_cluster_cache_sync,
)
from app.sql.db_pool import get_db_pool
from app.tools.cluster.config import (
    CACHE_TTL_SECONDS,
    FEATURE_COLUMN_MAP,
    LOADER_CACHE_MAX_CHARS,
    LOADER_CACHE_MAX_LOCATIONS,
    LOADER_CACHE_MAX_PAYLOAD_BYTES,
    LOADER_CACHE_TTL_SECONDS,
    TONE_SLOT_COLUMNS,
)
from app.tools.cluster.utils import chunked, dedupe, parse_coordinates, quote_identifier, safe_text

logger = logging.getLogger(__name__)


def cache_get_json(key: str) -> Optional[Any]:
    """读取 cluster 内部使用的 JSON 缓存。"""
    return get_cluster_cache_sync(key)


def cache_set_json(key: str, value: Any, ttl: int = CACHE_TTL_SECONDS):
    """写入 cluster 内部使用的 JSON 缓存。"""
    set_cluster_cache_sync(key, value, expire_seconds=ttl)


def build_filters_cache_key(group: Dict[str, Any]) -> str:
    """为旧版 structured filters 输入生成稳定缓存 key。"""
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
    """
    解析 charlist 风格的 `path_strings` 输入。

    这里刻意直接复用 `/api/charlist` 同源的 key 生成与解析逻辑，
    这样 cluster 和 charlist 可以命中同一份 Redis 缓存。
    """
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
    """
    兼容旧版 structured filters 输入。

    这条路径仍然保留兼容，但当前前端主路径已经更偏向 charlist 风格输入。
    """
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

    # OR 在字段内展开，AND 在字段之间合并，保持与旧查询约定一致。
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


def load_location_filter_details(
    locations: Sequence[str],
    db_path: str,
) -> Dict[str, Dict[str, Any]]:
    """
    读取地点过滤阶段需要的最小字段。

    这里只查简称和分区信息，因为 resolver 阶段只需要判断：
    - 是否命中地点；
    - 是否属于默认要过滤的特殊点。
    """
    details: Dict[str, Dict[str, Any]] = {}
    if not locations:
        return details

    columns = ["簡稱", "音典分區", "地圖集二分區"]
    quoted_columns = ", ".join(quote_identifier(column) for column in columns)

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        for batch in chunked(list(locations), 120):
            placeholders = ",".join("?" * len(batch))
            cursor.execute(
                f"""
                SELECT {quoted_columns}
                FROM dialects
                WHERE 簡稱 IN ({placeholders})
                """,
                list(batch),
            )
            for row in cursor.fetchall():
                location = safe_text(row[0])
                if not location:
                    continue
                details[location] = {
                    "location": location,
                    "yindian_region": safe_text(row[1]),
                    "map_region": safe_text(row[2]),
                }

    for location in locations:
        if location not in details:
            details[location] = {
                "location": location,
                "yindian_region": None,
                "map_region": None,
            }
    return details


def load_location_details(
    locations: Sequence[str],
    db_path: str,
) -> Dict[str, Dict[str, Any]]:
    """
    读取结果展示所需的地点详情。

    这些字段不参与聚类计算，只用于最后的 assignments / location_details 展示，
    所以在主流程中会被延后到距离矩阵计算之后再查询。
    """
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


def _can_cache_loader_payload(
    locations: Sequence[str],
    chars: Sequence[str],
) -> bool:
    """只允许中小请求进入 loader 缓存，避免 Redis 爆大对象。"""
    return (
        len(locations) <= LOADER_CACHE_MAX_LOCATIONS
        and len(chars) <= LOADER_CACHE_MAX_CHARS
    )


def _build_loader_cache_key(
    locations: Sequence[str],
    chars: Sequence[str],
    db_path: str,
    resolved_dimensions: Sequence[str],
) -> str:
    """根据地点、字集、数据库和维度集合生成 loader 缓存 key。"""
    payload = {
        "db": str(db_path),
        "locations": list(locations),
        "chars": list(chars),
        "dimensions": list(resolved_dimensions),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "cluster:loader:v1:" + hashlib.sha256(encoded).hexdigest()


def _serialize_dialect_data(
    data: Dict[str, Dict[str, Dict[str, set[str]]]],
) -> Dict[str, Dict[str, Dict[str, list[str]]]]:
    """把内部 `set` 结构转成可序列化的列表结构。"""
    serialized: Dict[str, Dict[str, Dict[str, list[str]]]] = {}
    for location, char_map in data.items():
        serialized[location] = {}
        for char, dimension_map in char_map.items():
            serialized[location][char] = {
                dimension: sorted(values)
                for dimension, values in dimension_map.items()
                if values
            }
    return serialized


def _deserialize_dialect_data(
    payload: Dict[str, Dict[str, Dict[str, Sequence[str]]]],
) -> Dict[str, Dict[str, Dict[str, set[str]]]]:
    """把缓存中的 JSON 结构恢复成内部使用的多层 `set` 结构。"""
    deserialized: Dict[str, Dict[str, Dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: {"initial": set(), "final": set(), "tone": set()})
    )
    for location, char_map in payload.items():
        for char, dimension_map in char_map.items():
            for dimension, values in dimension_map.items():
                if dimension in FEATURE_COLUMN_MAP:
                    deserialized[location][char][dimension] = {
                        str(value).strip()
                        for value in values or []
                        if str(value).strip()
                    }
    return deserialized


def load_dialect_rows(
    locations: Sequence[str],
    chars: Sequence[str],
    db_path: str,
    requested_dimensions: Optional[Sequence[str]] = None,
) -> Dict[str, Dict[str, Dict[str, set[str]]]]:
    """
    批量读取 cluster 需要的方言行数据。

    返回结构固定为：
    `location -> char -> dimension -> set[str]`

    关键点有两个：
    1. 只读取当前请求真正用到的维度列；
    2. SQL 采用 temp table + `IN (SELECT ...)` 形态，避免对 `dialects` 走全表扫描。
    """
    data: Dict[str, Dict[str, Dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: {"initial": set(), "final": set(), "tone": set()})
    )
    if not locations or not chars:
        return data

    # 如果调用方没有显式给维度，就回退到三维全读，以保持兼容。
    resolved_dimensions = [
        dimension
        for dimension in sorted(set(requested_dimensions or FEATURE_COLUMN_MAP.keys()))
        if dimension in FEATURE_COLUMN_MAP
    ]
    if not resolved_dimensions:
        return data

    # loader 缓存只覆盖中小请求；全量请求即使重复，也不把巨大 payload 写进 Redis。
    loader_cache_key: Optional[str] = None
    if _can_cache_loader_payload(locations, chars):
        loader_cache_key = _build_loader_cache_key(
            locations,
            chars,
            db_path,
            resolved_dimensions,
        )
        cached_payload = cache_get_json(loader_cache_key)
        if isinstance(cached_payload, dict):
            return _deserialize_dialect_data(cached_payload)

    # SELECT 列动态裁剪，例如只比韵母时就只取 `韻母` 一列。
    selected_columns = ["簡稱", "漢字"] + [
        quote_identifier(FEATURE_COLUMN_MAP[dimension])
        for dimension in resolved_dimensions
    ]
    select_clause = ", ".join(selected_columns)

    list_locations = list(locations)
    list_chars = list(chars)

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # 使用 chunked 分区直查，避免 CREATE TEMP TABLE 引发磁盘 I/O 和 SQLite IN(SELECT) 查询规划退化。
        # SQLite 的参数上限较高，这里将 char/location 维度安全切分，直接走原生参数绑定确保最优覆盖索引。
        for chars_batch in chunked(list_chars, 10000):
            chars_placeholders = ",".join("?" * len(chars_batch))
            for locations_batch in chunked(list_locations, 400):
                locations_placeholders = ",".join("?" * len(locations_batch))

                query = f"""
                    SELECT {select_clause}
                    FROM dialects
                    WHERE 簡稱 IN ({locations_placeholders})
                      AND 漢字 IN ({chars_placeholders})
                """
                params = list(locations_batch) + list(chars_batch)
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    location = row[0]
                    char = row[1]
                    char_dict = data[location][char]  # 通过指针引用加速写入，避免深层 defaultdict 多次求值
                    for offset, dimension in enumerate(resolved_dimensions, start=2):
                        raw_value = row[offset]
                        if raw_value:
                            char_dict[dimension].add(str(raw_value).strip())

    # 只有序列化体积仍在阈值内时才写缓存，继续兜住 Redis 体积风险。
    if loader_cache_key:
        serialized_payload = _serialize_dialect_data(data)
        payload_bytes = len(
            json.dumps(
                serialized_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if payload_bytes <= LOADER_CACHE_MAX_PAYLOAD_BYTES:
            cache_set_json(
                loader_cache_key,
                serialized_payload,
                ttl=LOADER_CACHE_TTL_SECONDS,
            )
    return data


def load_dimension_inventory_profiles(
    locations: Sequence[str],
    dimensions: Sequence[str],
    db_path: str,
) -> Dict[str, Dict[str, Dict[str, Dict[str, float]]]]:
    """
    读取每个地点在某个维度上的“整体库存画像”。

    anchored_inventory 模式会用它来回答：
    “某个 token 在该地点内部是高频还是低频、核心还是边缘？”
    """
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

            # 对每个地点，把原始频次进一步折算成 share / rank_pct / count 三类指标。
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
