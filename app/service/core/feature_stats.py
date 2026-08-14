# app/service/feature_stats.py
"""
特征统计服务

提供音韵特征的统计分析功能，包括：
1. get_feature_counts() - 简单的特征计数（从 phonology2status.py 迁移）
2. get_feature_statistics() - 详细的特征统计分析（新功能）

Author: Claude Code
Created: 2026-02-14
"""

from collections import defaultdict
import re
from typing import List, Dict, Optional, Set, Iterable
import hashlib

from app.sql.db_pool import get_db_pool
from app.common.constants import POLYPHONIC_MARKS, WENDU_MARKS, BAIDU_MARKS
from app.service.core.matrix import custom_phonology_sort
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations
from app.service.geo.match_input_tip import match_locations_batch_exact


def _mark_to_text(value) -> str:
    return "" if value is None else str(value).strip()


def _is_polyphonic_mark(value) -> bool:
    return _mark_to_text(value) in POLYPHONIC_MARKS


def _is_wendu_mark(value) -> bool:
    return _mark_to_text(value) in WENDU_MARKS


def _is_baidu_mark(value) -> bool:
    return _mark_to_text(value) in BAIDU_MARKS


def _read_stats_from_sets(read_bucket: Dict, char_to_index: Dict[str, int]) -> Dict:
    marks_by_char = read_bucket.get("_marks_by_char", {})
    wenbai_chars = {
        char
        for char, marks in marks_by_char.items()
        if marks & WENDU_MARKS and marks & BAIDU_MARKS
    }

    def build(chars: Set[str]) -> Dict:
        indices = sorted(char_to_index[char] for char in chars if char in char_to_index)
        return {"count": len(indices), "char_indices": indices}

    return {
        "polyphonic": build(read_bucket.get("polyphonic", set())),
        "wendu": build(read_bucket.get("wendu", set())),
        "baidu": build(read_bucket.get("baidu", set())),
        "wenbai": build(wenbai_chars),
    }


def _chunked(items: List[str], chunk_size: int = 500) -> Iterable[List[str]]:
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def _clean_text(value) -> str:
    return "" if value is None else str(value).strip()


def _dedupe_preserving_order(items: Iterable[str]) -> List[str]:
    result = []
    seen = set()
    for item in items or []:
        text = _clean_text(item)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def resolve_feature_locations(
    locations: Optional[List[str]],
    regions: Optional[List[str]],
    query_db_path: str,
    region_mode: str = "yindian",
) -> List[str]:
    """Resolve regions and locations to valid dialect abbrs, matching ZhongGu."""
    resolved = query_dialect_abbreviations(
        region_input=regions,
        location_sequence=locations or [],
        db_path=query_db_path,
        region_mode=region_mode,
    )
    match_results = match_locations_batch_exact(" ".join(resolved), query_db=query_db_path)
    abbrs = [abbr for res in match_results for abbr in res[0]]
    return _dedupe_preserving_order(abbrs)


def get_feature_counts(locations, db_path, table="dialects", chunk_size: int = 500):
    """
    按特征各跑一条 GROUP BY COUNT(DISTINCT 漢字)，命中覆盖索引，参数=地点数（不乘 3）。

    [MIGRATED FROM] app.service.phonology2status.py
    此函数已从 phonology2status.py 迁移到此处，用于集中管理特征统计功能。

    Args:
        locations: 地点列表
        db_path: 数据库路径
        table: 表名

    Returns:
        {
            "地点1": {
                "聲母": {"p": 150, "b": 120, ...},
                "韻母": {"a": 200, "ɐ": 180, ...},
                "聲調": {"陰平": 500, "陽平": 480, ...}
            },
            ...
        }
    """
    locations = _dedupe_preserving_order(locations)
    result = defaultdict(lambda: defaultdict(dict))
    if not locations:
        return result

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        for chunk in _chunked(locations, chunk_size):
            placeholders = ",".join(["?"] * len(chunk))
            for feature in ("聲母", "韻母", "聲調"):
                cursor.execute(
                    f"SELECT 簡稱, {feature}, COUNT(DISTINCT 漢字) FROM {table} "
                    f"WHERE 簡稱 IN ({placeholders}) GROUP BY 簡稱, {feature}",
                    chunk,
                )
                for loc, value, count in cursor.fetchall():
                    loc = _clean_text(loc)
                    value = _clean_text(value)
                    if not loc or not value:
                        continue
                    result[loc][feature][value] = int(count or 0)

    ordered_result = defaultdict(lambda: defaultdict(dict))
    for location in locations:
        if location in result:
            ordered_result[location] = result[location]

    return ordered_result


def get_feature_counts_for_request(
    locations: Optional[List[str]],
    regions: Optional[List[str]],
    new_format: bool,
    dialects_db: str,
    query_db: str,
    region_mode: str = "yindian",
):
    """Resolve feature-count request inputs while preserving the legacy output format."""
    clean_locations = _dedupe_preserving_order(locations or [])
    clean_regions = _dedupe_preserving_order(regions or [])
    if not clean_locations and not clean_regions:
        raise ValueError("locations 和 regions 不能同時為空，至少提供其一")

    resolved_locations = resolve_feature_locations(
        locations=clean_locations,
        regions=clean_regions,
        query_db_path=query_db,
        region_mode=region_mode,
    )
    result = get_feature_counts(resolved_locations, dialects_db)

    if not new_format:
        return result

    ordered = list(result.keys())
    abbr_to_id = {abbr: i for i, abbr in enumerate(ordered)}
    return {
        "locations": result,
        "aggregated": calculate_aggregated_feature_counts(result, abbr_to_id),
    }


def _parse_coordinate(value) -> Optional[List[float]]:
    text = _clean_text(value)
    if not text:
        return None
    parts = [part for part in re.split(r"[,，;；\s]+", text) if part]
    if len(parts) < 2:
        return None
    try:
        latitude = float(parts[0])
        longitude = float(parts[1])
    except ValueError:
        return None
    return [latitude, longitude]


def _fetch_location_coordinates(
    locations: List[str],
    db_path: str,
    table: str = "dialects",
    chunk_size: int = 500,
) -> Dict[str, Optional[List[float]]]:
    coordinates = {}
    if not locations:
        return coordinates

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        for chunk in _chunked(locations, chunk_size):
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(
                f"SELECT 簡稱, 經緯度 FROM {table} WHERE 簡稱 IN ({placeholders})",
                chunk,
            )
            for row in cursor.fetchall():
                if row[0] not in coordinates:
                    coordinates[row[0]] = _parse_coordinate(row[1])

    return coordinates


def _build_location_id_map(locations: List[str], query_db_path: str, chunk_size: int = 500) -> tuple:
    """id = locations 顺序下标；返回 (id_to_info, abbr_to_id)。"""
    coordinates = _fetch_location_coordinates(locations, query_db_path, chunk_size=chunk_size)
    id_to_info = {}
    abbr_to_id = {}
    for i, abbr in enumerate(locations):
        id_to_info[i] = {"id": i, "location": abbr, "coordinate": coordinates.get(abbr)}
        abbr_to_id[abbr] = i
    return id_to_info, abbr_to_id


def _build_syllable_section(
    location_counts: Dict[str, Dict[str, int]],
    locations: List[str],
    abbr_to_id: Optional[Dict[str, int]] = None,
) -> Dict:
    location_payload = {}
    aggregated_syllables = defaultdict(
        lambda: {"totalCount": 0, "locationCount": 0, "locations": []}
    )
    total_tokens = 0
    all_syllables = set()

    for location in locations:
        syllables = dict(location_counts.get(location, {}))
        location_total = sum(int(count or 0) for count in syllables.values())
        location_unique = len(syllables)
        location_payload[location] = {
            "total_tokens": location_total,
            "unique_syllables": location_unique,
            "syllables": syllables,
        }
        total_tokens += location_total
        all_syllables.update(syllables.keys())

        for syllable, count in syllables.items():
            count = int(count or 0)
            if count <= 0:
                continue
            item = aggregated_syllables[syllable]
            item["totalCount"] += count
            item["locationCount"] += 1
            item["locations"].append(
                abbr_to_id[location] if abbr_to_id is not None else location
            )

    return {
        "locations": location_payload,
        "aggregated": {
            "total_tokens": total_tokens,
            "unique_syllables": len(all_syllables),
            "syllables": dict(aggregated_syllables),
        },
    }


def get_syllable_counts(
    locations: List[str],
    dialects_db_path: str,
    query_db_path: str,
    table: str = "dialects",
    chunk_size: int = 500,
    variant: str = "both",
    normalize_onset: bool = False,
) -> Dict:
    """
    Count toned and/or toneless syllables across locations, aggregated in SQL.

    ``variant`` selects which payload(s) to return: ``"both"`` (default),
    ``"toneless"``, or ``"toned"``. Toned and toneless are computed by fully
    separate queries, so requesting a single variant avoids the other's I/O.

    ``normalize_onset`` is off by default (the raw 音節 / 聲母+韻母 keys the
    frontend expects). When enabled, the onset (聲母) is normalized so the
    various zero/glottal notations collapse onto one canonical initial, leaving
    the 韻母 untouched: ``ʔw``→``w``; ``ʔj``→``j``; the zero/glottal initials
    ``/``, ``ʔ``, ``ˀ`` (and 音節 spellings ``∅``) become ``w`` before ``u``,
    ``j`` before ``i``/``y``, else ``ʔ``. Toned keys strip the onset from 音節 by
    its known width (0 for ``/``, 1 for ``ʔ``/``ˀ``, 2 for ``ʔw``/``ʔj``) and
    re-prepend the canonical initial, so the 音節's own vowel/tone encoding is
    preserved verbatim.

    Counts use COUNT(DISTINCT 漢字) semantics (a per-location per-syllable set of
    漢字), matching feature_counts semantics and avoiding duplicate rows for the
    same character/pronunciation from inflating token counts.
    """
    if variant not in ("both", "toneless", "toned"):
        raise ValueError(f"invalid variant: {variant!r}")

    requested_locations = _dedupe_preserving_order(locations)
    want_toneless = variant in ("both", "toneless")
    want_toned = variant in ("both", "toned")

    if normalize_onset:
        toned_key = (
            "CASE "
            "WHEN TRIM(聲母) = 'ʔw' THEN 'w' || substr(音節, 3) "
            "WHEN TRIM(聲母) = 'ʔj' THEN 'j' || substr(音節, 3) "
            "WHEN TRIM(聲母) IN ('/', 'ʔ', 'ˀ') THEN "
            "CASE substr(COALESCE(TRIM(韻母), ''), 1, 1) "
            "WHEN 'u' THEN 'w' WHEN 'i' THEN 'j' WHEN 'y' THEN 'j' ELSE 'ʔ' END "
            "|| substr(音節, CASE WHEN TRIM(聲母) = '/' THEN 1 ELSE 2 END) "
            "ELSE 音節 END"
        )
        toneless_key = (
            "CASE "
            "WHEN TRIM(聲母) = 'ʔw' THEN 'w' || COALESCE(TRIM(韻母), '') "
            "WHEN TRIM(聲母) = 'ʔj' THEN 'j' || COALESCE(TRIM(韻母), '') "
            "WHEN TRIM(聲母) IN ('/', 'ʔ', 'ˀ') THEN "
            "CASE substr(COALESCE(TRIM(韻母), ''), 1, 1) "
            "WHEN 'u' THEN 'w' WHEN 'i' THEN 'j' WHEN 'y' THEN 'j' ELSE 'ʔ' END "
            "|| COALESCE(TRIM(韻母), '') "
            "ELSE COALESCE(TRIM(聲母), '') || COALESCE(TRIM(韻母), '') END"
        )
    else:
        toned_key = "音節"
        toneless_key = "COALESCE(TRIM(聲母), '') || COALESCE(TRIM(韻母), '')"

    toneless_counts = defaultdict(dict)
    toned_counts = defaultdict(dict)

    pool = get_db_pool(dialects_db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        for chunk in _chunked(requested_locations, chunk_size):
            placeholders = ",".join(["?"] * len(chunk))
            if want_toned:
                cursor.execute(
                    f"SELECT 簡稱, {toned_key} AS k, COUNT(DISTINCT 漢字) FROM {table} "
                    f"WHERE 簡稱 IN ({placeholders}) "
                    f"AND 漢字 IS NOT NULL AND 漢字 <> '' "
                    f"AND 音節 IS NOT NULL AND 音節 <> '' "
                    f"GROUP BY 簡稱, k",
                    chunk,
                )
                for loc, syllable, count in cursor.fetchall():
                    loc = _clean_text(loc)
                    syllable = _clean_text(syllable)
                    if not loc or not syllable:
                        continue
                    toned_counts[loc][syllable] = int(count or 0)

            if want_toneless:
                cursor.execute(
                    f"SELECT 簡稱, {toneless_key} AS k, COUNT(DISTINCT 漢字) FROM {table} "
                    f"WHERE 簡稱 IN ({placeholders}) "
                    f"AND 漢字 IS NOT NULL AND 漢字 <> '' "
                    f"AND (COALESCE(TRIM(聲母), '') <> '' OR COALESCE(TRIM(韻母), '') <> '') "
                    f"GROUP BY 簡稱, k",
                    chunk,
                )
                for loc, key, count in cursor.fetchall():
                    loc = _clean_text(loc)
                    key = _clean_text(key)
                    if not loc or not key:
                        continue
                    toneless_counts[loc][key] = int(count or 0)

    locations_with_data = [
        location
        for location in requested_locations
        if location in toneless_counts or location in toned_counts
    ]
    id_to_info, abbr_to_id = _build_location_id_map(locations_with_data, query_db_path, chunk_size=chunk_size)
    locations_without_coordinates = [
        info["location"] for info in id_to_info.values() if info["coordinate"] is None
    ]

    result = {}
    if want_toneless:
        result["toneless"] = _build_syllable_section(toneless_counts, locations_with_data, abbr_to_id)
    if want_toned:
        result["toned"] = _build_syllable_section(toned_counts, locations_with_data, abbr_to_id)
    result["points"] = list(id_to_info.values())
    result["meta"] = {
        "requested_locations_count": len(requested_locations),
        "locations_count": len(locations_with_data),
        "locations_without_coordinates": locations_without_coordinates,
    }
    return result

def calculate_aggregated_feature_counts(location_data, abbr_to_id: Optional[Dict[str, int]] = None):
    """
    根据地点维度的原始统计数据，计算汇总数据。

    输入：
    {
        "广州": {
            "聲母": {"p": 10, "t": 8},
            "韻母": {"a": 12}
        },
        "香港": {
            "聲母": {"p": 7},
            "韻母": {"a": 9}
        }
    }

    输出（abbr_to_id 提供时 locations 为地点 id，否则为地点全称）：
    {
        "聲母": {
            "p": {
                "totalCount": 17,
                "locationCount": 2,
                "locations": [0, 1]
            },
            "t": {
                "totalCount": 8,
                "locationCount": 1,
                "locations": [0]
            }
        }
    }
    """
    aggregated = defaultdict(lambda: defaultdict(lambda: {
        "totalCount": 0,
        "locationCount": 0,
        "locations": []
    }))

    for location_name, location_data_item in (location_data or {}).items():
        for feature_type, features in (location_data_item or {}).items():
            for syllable, count in (features or {}).items():
                count = int(count or 0)
                if count <= 0:
                    continue

                item = aggregated[feature_type][syllable]
                item["totalCount"] += count
                item["locationCount"] += 1
                item["locations"].append(
                    abbr_to_id[location_name] if abbr_to_id is not None else location_name
                )

    # 转成普通 dict，避免 defaultdict 返回到前端
    return {
        feature_type: dict(features)
        for feature_type, features in aggregated.items()
    }


def get_feature_statistics(
    locations: List[str],
    chars: Optional[List[str]] = None,
    features: Optional[List[str]] = None,
    filters: Optional[Dict[str, List[str]]] = None,
    db_path: str = None,
    table: str = "dialects"
) -> Dict:
    """
    获取指定地点的音韵特征统计数据（索引优化格式）

    核心功能：
    1. 使用 UNION ALL 优化查询（将3次表扫描合并为1次）
    2. 返回索引优化格式（chars_map + char_indices）减少数据重复
    3. 支持汉字筛选和特征值筛选
    4. 计算每个特征值的数量和占比
    5. 使用 custom_phonology_sort() 对特征值排序

    Args:
        locations: 地点简称列表（必需）
        chars: 要查询的汉字列表（可选，为空则查该地点所有汉字）
        features: 要统计的特征列表（可选，默认 ["聲母", "韻母", "聲調"]）
        filters: 筛选条件（可选），例如 {"聲母": ["p", "b"], "韻母": ["a"]}
        db_path: 数据库路径
        table: 表名

    Returns:
        {
            "chars_map": ["八", "把", "白", ...],  # 全局字符字典
            "data": {
                "廣州": {
                    "total_chars": 3000,
                    "聲母": {
                        "p": {
                            "count": 150,
                            "ratio": 0.05,
                            "char_indices": [0, 1, 2, ...]  # 索引指向chars_map
                        },
                        ...
                    },
                    "韻母": {...},
                    "聲調": {...}
                }
            },
            "meta": {
                "query_chars_count": 2,
                "locations_count": 2,
                "has_filters": False
            }
        }
    """
    # 默认查询所有特征
    if features is None:
        features = ["聲母", "韻母", "聲調"]

    # 验证 features 参数
    valid_features = {"聲母", "韻母", "聲調"}
    invalid = set(features) - valid_features
    if invalid:
        raise ValueError(f"无效的特征类型: {invalid}，必须是 {valid_features}")

    # 构建SQL查询
    query_parts = []
    params = []

    for feature in features:
        # 基础查询
        where_clauses = [f"簡稱 IN ({','.join(['?' for _ in locations])})"]
        feature_params = list(locations)

        # 添加汉字筛选
        if chars:
            char_placeholders = ','.join(['?' for _ in chars])
            where_clauses.append(f"漢字 IN ({char_placeholders})")
            feature_params.extend(chars)

        # 添加特征值筛选
        if filters and feature in filters:
            filter_values = filters[feature]
            filter_placeholders = ','.join(['?' for _ in filter_values])
            where_clauses.append(f"{feature} IN ({filter_placeholders})")
            feature_params.extend(filter_values)

        # 组装单个特征的查询
        where_clause = " AND ".join(where_clauses)
        query_part = f"""
            SELECT 簡稱, '{feature}' as feature_type, {feature} as value, 漢字, 多音字
            FROM {table}
            WHERE {where_clause}
              AND {feature} IS NOT NULL
        """

        query_parts.append(query_part)
        params.extend(feature_params)

    # 使用 UNION ALL 合并查询
    query_combined = "\n\nUNION ALL\n\n".join(query_parts)

    # 执行查询
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query_combined, params)
        all_rows = cursor.fetchall()

    # 构建全局 chars_map（所有唯一汉字）
    all_chars_set: Set[str] = set()
    for row in all_rows:
        char = row[3]  # 漢字
        if char:
            all_chars_set.add(char)

    # 排序后生成 chars_map
    chars_map = sorted(list(all_chars_set))

    # 创建反向索引（字符 -> 索引）
    char_to_index = {char: idx for idx, char in enumerate(chars_map)}

    # 按 (location, feature_type, value) 分组数据
    grouped_data = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    read_grouped = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: {
                    "polyphonic": set(),
                    "wendu": set(),
                    "baidu": set(),
                    "_marks_by_char": defaultdict(set),
                }
            )
        )
    )

    for row in all_rows:
        location = row[0]    # 簡稱
        feature_type = row[1]  # feature_type
        value = row[2]       # 特征值
        char = row[3]        # 漢字
        mark = row[4]        # 多音字

        if not location or not feature_type or not value or not char:
            continue

        grouped_data[location][feature_type][value].add(char)
        read_bucket = read_grouped[location][feature_type][value]
        mark_text = _mark_to_text(mark)

        if _is_polyphonic_mark(mark_text):
            read_bucket["polyphonic"].add(char)
            read_bucket["_marks_by_char"][char].add(mark_text)
        if _is_wendu_mark(mark_text):
            read_bucket["wendu"].add(char)
        if _is_baidu_mark(mark_text):
            read_bucket["baidu"].add(char)

    # 计算每个地点的分母（total_chars）
    denominators = _calculate_denominators(locations, chars, filters, db_path, table)

    # 构建最终结果
    result_data = {}

    for location in locations:
        loc_data = {
            "total_chars": denominators.get(location, 0)
        }

        for feature in features:
            feature_dict = {}

            # 获取该地点该特征的所有值
            feature_values = grouped_data[location][feature]

            # 使用 custom_phonology_sort 排序特征值
            sorted_values = custom_phonology_sort(list(feature_values.keys()))

            for value in sorted_values:
                chars_set = feature_values[value]
                count = len(chars_set)

                # 计算占比
                total = denominators.get(location, 0)
                ratio = round(count / total, 4) if total > 0 else 0.0

                # 转换为索引列表
                char_indices = sorted([char_to_index[char] for char in chars_set])

                feature_dict[value] = {
                    "count": count,
                    "ratio": ratio,
                    "char_indices": char_indices,
                    "read_stats": _read_stats_from_sets(
                        read_grouped[location][feature][value],
                        char_to_index,
                    ),
                }

            loc_data[feature] = feature_dict

        result_data[location] = loc_data

    # 返回结果
    return {
        "chars_map": chars_map,
        "data": result_data,
        "meta": {
            "query_chars_count": len(chars) if chars else 0,
            "locations_count": len(locations),
            "has_filters": bool(filters)
        }
    }


def _calculate_denominators(
    locations: List[str],
    chars: Optional[List[str]],
    filters: Optional[Dict[str, List[str]]],
    db_path: str,
    table: str
) -> Dict[str, int]:
    """
    计算每个地点的分母（用于计算占比）

    规则：
    - 无筛选：分母 = 该地点所有汉字数
    - 有 chars 参数：分母 = len(chars)
    - 有 filters 参数：分母 = 该地点筛选后的汉字数

    Args:
        locations: 地点列表
        chars: 汉字筛选
        filters: 特征值筛选
        db_path: 数据库路径
        table: 表名

    Returns:
        {"地点1": 3000, "地点2": 2800, ...}
    """
    denominators = {}

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        for location in locations:
            # 构建查询条件
            where_clauses = ["簡稱 = ?"]
            params = [location]

            # 添加汉字筛选
            if chars:
                char_placeholders = ','.join(['?' for _ in chars])
                where_clauses.append(f"漢字 IN ({char_placeholders})")
                params.extend(chars)

            # 添加特征值筛选（任一特征匹配即可）
            if filters:
                filter_conditions = []
                for feature, values in filters.items():
                    value_placeholders = ','.join(['?' for _ in values])
                    filter_conditions.append(f"{feature} IN ({value_placeholders})")
                    params.extend(values)

                # 使用 OR 连接多个特征筛选
                if filter_conditions:
                    where_clauses.append(f"({' OR '.join(filter_conditions)})")

            # 组装查询
            where_clause = " AND ".join(where_clauses)
            query = f"""
                SELECT COUNT(DISTINCT 漢字)
                FROM {table}
                WHERE {where_clause}
            """

            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            denominators[location] = count

    return denominators


def generate_cache_key(
    db_type: str,
    locations: List[str],
    chars: Optional[List[str]],
    features: Optional[List[str]],
    filters: Optional[Dict[str, List[str]]]
) -> str:
    """
    生成缓存键（使用哈希避免键过长）

    Args:
        db_type: "admin" or "user"
        locations: 地点列表
        chars: 汉字列表
        features: 特征列表
        filters: 筛选条件

    Returns:
        "feature_stats:admin:abc123def456..."
    """
    # 构建确定性的字符串表示
    parts = [
        db_type,
        ",".join(sorted(locations)),
        ",".join(sorted(chars)) if chars else "",
        ",".join(sorted(features)) if features else "",
    ]

    # 添加 filters（排序后序列化）
    if filters:
        filter_str = "|".join([
            f"{k}:{','.join(sorted(v))}"
            for k, v in sorted(filters.items())
        ])
        parts.append(filter_str)
    else:
        parts.append("")

    # 拼接并哈希
    combined = ":".join(parts)
    hash_value = hashlib.md5(combined.encode()).hexdigest()[:16]

    return f"feature_stats:{db_type}:{hash_value}"
