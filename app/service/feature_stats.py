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
from typing import List, Dict, Optional, Set
import hashlib

from app.sql.db_pool import get_db_pool
from app.service.phonology2status import custom_phonology_sort


def get_feature_counts(locations, db_path, table="dialects"):
    """
    优化版本：使用 UNION ALL 将三次表扫描合并为一次查询
    显著提升查询性能（3次扫描 → 1次扫描）

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
    result = defaultdict(lambda: defaultdict(dict))

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # [OK] 优化：使用 UNION ALL 合并三个查询为一次表扫描
        placeholders = ','.join(['?' for _ in locations])

        query_combined = f"""
            SELECT 簡稱, '聲母' as feature_type, 聲母 as value, COUNT(DISTINCT 漢字) AS 字數
            FROM {table}
            WHERE 簡稱 IN ({placeholders})
            GROUP BY 簡稱, 聲母

            UNION ALL

            SELECT 簡稱, '韻母' as feature_type, 韻母 as value, COUNT(DISTINCT 漢字) AS 字數
            FROM {table}
            WHERE 簡稱 IN ({placeholders})
            GROUP BY 簡稱, 韻母

            UNION ALL

            SELECT 簡稱, '聲調' as feature_type, 聲調 as value, COUNT(DISTINCT 漢字) AS 字數
            FROM {table}
            WHERE 簡稱 IN ({placeholders})
            GROUP BY 簡稱, 聲調
        """

        # 执行合并后的查询（参数需要重复3次，对应3个WHERE子句）
        cursor.execute(query_combined, locations * 3)

        # 处理所有结果，按特征类型分离
        all_rows = cursor.fetchall()
        for row in all_rows:
            loc = row[0]
            feature_type = row[1]
            value = row[2]
            count = row[3]

            # 根据特征类型填充结果字典
            result[loc][feature_type][value] = count

    return result


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
            SELECT 簡稱, '{feature}' as feature_type, {feature} as value, 漢字
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

    for row in all_rows:
        location = row[0]    # 簡稱
        feature_type = row[1]  # feature_type
        value = row[2]       # 特征值
        char = row[3]        # 漢字

        if not location or not feature_type or not value or not char:
            continue

        grouped_data[location][feature_type][value].add(char)

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
                    "char_indices": char_indices
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
