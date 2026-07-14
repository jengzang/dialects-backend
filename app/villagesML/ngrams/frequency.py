"""
N-gram分析API
N-gram Analysis API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, Dict, Any
import sqlite3
from itertools import groupby
from collections import OrderedDict

from ..dependencies import get_db, get_dbpath, execute_query
from ..schema_runtime import qcolumn, qtable
from ..schema_keys import C, T

router = APIRouter(prefix="/ngrams")

# PRAGMA 缓存：避免每次请求都查询 schema
_pragma_cache: Dict[str, Any] = {}

# 数据优化配置
DATA_OPTIMIZATION_DATE = None  # 将在数据优化后设置，格式: "2026-02-25"
DATA_RETENTION_RATE = 1.0  # 数据保留率，优化后会更新为 0.587
INCLUDES_INSIGNIFICANT = True  # 是否包含不显著数据，优化后会设置为 False


def _ngram_schema(dbpath: str, logical_table: str):
    return qtable(dbpath, logical_table), lambda name: qcolumn(dbpath, logical_table, name)


def _build_metadata(
    total_count: int,
    includes_insignificant: bool = INCLUDES_INSIGNIFICANT
) -> Dict[str, Any]:
    """
    构建响应元数据

    Args:
        total_count: 返回的记录数
        includes_insignificant: 是否包含不显著数据

    Returns:
        元数据字典
    """
    metadata = {
        "total_count": total_count,
        "includes_insignificant": includes_insignificant
    }

    if DATA_OPTIMIZATION_DATE:
        metadata["note"] = "Only statistically significant n-grams (p < 0.05) are included"
        metadata["data_version"] = f"optimized_{DATA_OPTIMIZATION_DATE.replace('-', '')}"
        metadata["optimization_date"] = DATA_OPTIMIZATION_DATE
        metadata["coverage_rate"] = DATA_RETENTION_RATE

    return metadata


@router.get("/frequency")
def get_ngram_frequency(
    n: int = Query(..., ge=2, le=4, description="N-gram大小 (2=bigram, 3=trigram)"),
    position: str = Query("all", pattern="^(all|prefix|middle|suffix)$", description="N-gram位置 (all=所有位置, prefix=前缀, middle=中间, suffix=后缀)"),
    top_k: int = Query(100, ge=1, le=1000, description="返回前K个n-grams"),
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频次过滤"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取全局N-gram频率
    Get global n-gram frequencies

    Args:
        n: N-gram大小 (2, 3, 或 4)
        position: N-gram位置 (all=所有位置, prefix=前缀, middle=中间, suffix=后缀)
        top_k: 返回前K个高频n-grams
        min_frequency: 最小频次阈值（可选）

    Returns:
        List[dict]: N-gram频率列表
    """
    table, col = _ngram_schema(dbpath, T.NGRAM_FREQUENCY)
    query = f"""
        SELECT
            {col("ngram")} as ngram,
            {col("position")} as position,
            {col("frequency")} as frequency,
            {col("percentage")} as percentage
        FROM {table}
        WHERE {col("n")} = ? AND {col("position")} = ?
    """
    params = [n, position]

    # 现场过滤：最小频次
    if min_frequency is not None:
        query += f" AND {col('frequency')} >= ?"
        params.append(min_frequency)

    query += f" ORDER BY {col('frequency')} DESC LIMIT ?"
    params.append(top_k)

    # Debug: print the query
    # print(f"DEBUG: Query = {query}")
    # print(f"DEBUG: Params = {params}")

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No {n}-grams found"
        )

    return results


@router.get("/regional")
def get_regional_ngram_frequency(
    n: int = Query(..., ge=2, le=4, description="N-gram大小"),
    region_level: str = Query("township", description="区域级别（支持动态聚合）", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    top_k: int = Query(50, ge=1, le=500, description="每个区域返回前K个n-grams"),
    return_metadata: bool = Query(False, description="是否返回元数据（包含数据说明）"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取区域N-gram频率
    Get regional n-gram frequencies

    支持三种级别：
    - township: 直接查询乡镇级数据（原始数据）
    - county: 从乡镇数据动态聚合到区县级
    - city: 从乡镇数据动态聚合到市级

    Args:
        n: N-gram大小
        region_level: 区域级别 (city/county/township)
        region_name: 区域名称（模糊匹配，可选，向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        top_k: 每个区域返回前K个n-grams
        return_metadata: 是否返回元数据

    Returns:
        List[dict] 或 dict: N-gram频率列表，或包含data和metadata的字典
    """
    table, col = _ngram_schema(dbpath, T.REGIONAL_NGRAM_FREQUENCY)
    level_col = col("level")
    region_col = col("region")
    city_col = col("city")
    county_col = col("county")
    township_col = col("township")
    ngram_col = col("ngram")
    frequency_col = col("frequency")
    percentage_col = col("percentage")
    n_col = col("n")

    # 根据 region_level 构建不同的查询
    if region_level == "township":
        # Township 级别：直接查询原始数据
        query = f"""
            SELECT
                'township' as region_level,
                {region_col} as region_name,
                {city_col} as city,
                {county_col} as county,
                {township_col} as township,
                {ngram_col} as ngram,
                {frequency_col} as frequency,
                {percentage_col} as percentage
            FROM {table}
            WHERE {n_col} = ? AND {level_col} = 'township'
        """
        params = [n]

        # 过滤条件
        if city is not None:
            query += f" AND {city_col} = ?"
            params.append(city)
        if county is not None:
            query += f" AND {county_col} = ?"
            params.append(county)
        elif city is not None and region_level == 'township':
            # Handle 东莞市/中山市 (no county level)
            query += f" AND ({county_col} IS NULL OR {county_col} = '')"
        if township is not None:
            query += f" AND {township_col} = ?"
            params.append(township)
        if region_name is not None:
            query += f" AND {region_col} = ?"
            params.append(region_name)

        query += f" ORDER BY {region_col}, {frequency_col} DESC"

    elif region_level == "county":
        # County 级别：从 township 聚合
        query = f"""
            SELECT
                {county_col} as region_name,
                {city_col} as city,
                {county_col} as county,
                {ngram_col} as ngram,
                SUM({frequency_col}) as frequency,
                COUNT(*) as _town_count
            FROM {table}
            WHERE {n_col} = ? AND {level_col} = 'township'
        """
        params = [n]

        # 过滤条件
        if city is not None:
            query += f" AND {city_col} = ?"
            params.append(city)
        if county is not None:
            query += f" AND {county_col} = ?"
            params.append(county)
        if region_name is not None:
            query += f" AND {county_col} = ?"
            params.append(region_name)

        query += f" GROUP BY {county_col}, {city_col}, {ngram_col}"
        query += f" ORDER BY {county_col}, SUM({frequency_col}) DESC"

    else:  # region_level == "city"
        # City 级别：从 township 聚合
        query = f"""
            SELECT
                {city_col} as region_name,
                {city_col} as city,
                {ngram_col} as ngram,
                SUM({frequency_col}) as frequency,
                COUNT(*) as _town_count
            FROM {table}
            WHERE {n_col} = ? AND {level_col} = 'township'
        """
        params = [n]

        # 过滤条件
        if city is not None:
            query += f" AND {city_col} = ?"
            params.append(city)
        if region_name is not None:
            query += f" AND {city_col} = ?"
            params.append(region_name)

        query += f" GROUP BY {city_col}, {ngram_col}"
        query += f" ORDER BY {city_col}, SUM({frequency_col}) DESC"

    raw_rows = execute_query(db, query, tuple(params))

    # Python 侧 groupby 取每个 region 的 top_k，计算 percentage
    results = []
    for region_name_key, group in groupby(raw_rows, key=lambda r: r['region_name']):
        group_list = list(group)
        group_total = sum(r['frequency'] for r in group_list)
        for i, row in enumerate(group_list[:top_k]):
            entry = OrderedDict()
            entry['region_level'] = region_level
            entry['region_name'] = region_name_key
            entry['city'] = row.get('city')
            if region_level == 'township':
                entry['county'] = row.get('county')
                entry['township'] = row.get('township')
            elif region_level == 'county':
                entry['county'] = row.get('county')
                entry['township'] = None
            else:
                entry['county'] = None
                entry['township'] = None
            entry['ngram'] = row['ngram']
            entry['frequency'] = row['frequency']
            entry['percentage'] = round(row['frequency'] * 100.0 / group_total, 10) if group_total else 0.0
            entry['rank'] = i + 1
            results.append(entry)

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No regional {n}-grams found with the given filters."
        )

    # 如果需要返回元数据
    if return_metadata:
        metadata = _build_metadata(len(results))
        if region_level in ['city', 'county']:
            metadata['note'] = f"Data aggregated from township level to {region_level} level"
        return {
            "data": results,
            "metadata": metadata
        }

    return results


@router.get("/patterns")
def get_structural_patterns(
    pattern: Optional[str] = Query(None, description="模式过滤（*或X表示占位符，如'山*'或'山X'；支持SQL LIKE语法，如'山%'表示以山开头）"),
    pattern_type: Optional[str] = Query(None, description="模式类型过滤"),
    n: Optional[int] = Query(None, ge=2, le=4, description="N-gram大小过滤"),
    position: Optional[str] = Query(None, pattern="^(all|prefix|middle|suffix)$", description="位置过滤"),
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频次过滤"),
    limit: int = Query(100, ge=1, le=500, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取结构化命名模式
    Get structural naming patterns

    Args:
        pattern: 模式过滤（*或X表示占位符；支持SQL LIKE语法）
        pattern_type: 模式类型（可选）
        n: N-gram大小（可选）
        position: 位置过滤（可选）
        min_frequency: 最小频次（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 结构化模式列表
    """
    table, col = _ngram_schema(dbpath, T.STRUCTURAL_PATTERNS)
    query = f"""
        SELECT
            {col("pattern")} as pattern,
            {col("pattern_type")} as pattern_type,
            {col("n")} as n,
            {col("position")} as position,
            {col("frequency")} as frequency,
            {col("example")} as example
        FROM {table}
    """
    params = []

    # 现场过滤
    conditions = []

    # 模式过滤（支持 LIKE，同时支持 * 和 X 作为占位符）
    if pattern is not None:
        # 将 * 替换为 X（数据库中使用 X 作为占位符）
        normalized_pattern = pattern.replace('*', 'X')

        # 智能模糊匹配：如果不包含通配符（%、_、X），自动添加 % 进行模糊匹配
        if '%' not in normalized_pattern and '_' not in normalized_pattern and 'X' not in normalized_pattern:
            normalized_pattern = f'%{normalized_pattern}%'

        conditions.append(f"{col('pattern')} LIKE ?")
        params.append(normalized_pattern)

    # 模式类型过滤
    if pattern_type is not None:
        conditions.append(f"{col('pattern_type')} = ?")
        params.append(pattern_type)

    # N-gram 大小过滤
    if n is not None:
        conditions.append(f"{col('n')} = ?")
        params.append(n)

    # 位置过滤
    if position is not None:
        conditions.append(f"{col('position')} = ?")
        params.append(position)

    # 最小频次过滤
    if min_frequency is not None:
        conditions.append(f"{col('frequency')} >= ?")
        params.append(min_frequency)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += f" ORDER BY {col('frequency')} DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        # 提供更详细的错误信息
        error_msg = "No structural patterns found"
        if n is not None:
            error_msg += f" for n={n}"
        if pattern is not None:
            error_msg += f" matching pattern '{pattern}'"
        error_msg += ". Note: Currently only n=2 (bigram) patterns are available in the database."

        raise HTTPException(
            status_code=404,
            detail=error_msg
        )

    return results


@router.get("/tendency")
def get_ngram_tendency(
    ngram: Optional[str] = Query(None, description="N-gram（2-4字符，如'新村'、'村村'）"),
    region_level: str = Query("township", description="区域级别（支持动态聚合）", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    min_tendency: Optional[float] = Query(None, description="最小倾向值（lift值）"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取N-gram倾向性分析
    Get n-gram tendency scores

    支持三种级别：
    - township: 直接查询乡镇级数据（原始数据）
    - county: 从乡镇数据动态聚合到区县级
    - city: 从乡镇数据动态聚合到市级

    注意：
    - ngram 必须是 2-4 字符的组合（如"新村"、"山村"），不支持单字符
    - 倾向值 (lift) > 1 表示该区域偏好使用该 n-gram
    - 倾向值 (lift) < 1 表示该区域较少使用该 n-gram
    - 聚合级别的 lift 值会重新计算

    Args:
        ngram: N-gram内容（2-4字符）
        region_level: 区域级别（city/county/township）
        region_name: 区域名称（模糊匹配）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        min_tendency: 最小倾向值（lift值）
        limit: 返回记录数

    Returns:
        List[dict]: N-gram倾向性列表（包含区域中心点坐标）
    """

    # 检查 regional_total_raw 字段是否存在（缓存 PRAGMA 结果）
    tendency_table, tcol = _ngram_schema(dbpath, T.NGRAM_TENDENCY)
    centroids_table, ccol = _ngram_schema(dbpath, T.REGIONAL_CENTROIDS)
    cache_key = f"has_regional_total_raw:{dbpath}"
    if cache_key not in _pragma_cache:
        cursor = db.cursor()
        cursor.execute(f"PRAGMA table_info({tendency_table})")
        columns = [col[1] for col in cursor.fetchall()]
        _pragma_cache[cache_key] = qcolumn(dbpath, T.NGRAM_TENDENCY, C.NGRAM_TENDENCY.REGIONAL_TOTAL_RAW).strip('"') in columns
    has_regional_total_raw = _pragma_cache[cache_key]

    # 根据 region_level 构建不同的查询
    if region_level == "township":
        # Township 级别：直接查询原始数据
        regional_total_raw_field = f"nt.{tcol('regional_total_raw')}" if has_regional_total_raw else "NULL"

        query = f"""
            SELECT
                nt.{tcol('level')} as region_level,
                nt.{tcol('region')} as region_name,
                nt.{tcol('city')} as city,
                nt.{tcol('county')} as county,
                nt.{tcol('township')} as township,
                nt.{tcol('ngram')} as ngram,
                nt.{tcol('n')} as n,
                nt.{tcol('position')} as position,
                nt.{tcol('lift')} as tendency_score,
                nt.{tcol('log_odds')} as log_odds,
                nt.{tcol('z_score')} as z_score,
                nt.{tcol('regional_count')} as frequency,
                nt.{tcol('regional_total')} as regional_total,
                {regional_total_raw_field} as regional_total_raw,
                nt.{tcol('global_count')} as expected_frequency,
                nt.{tcol('global_total')} as global_total,
                rc.{ccol('centroid_lon')} as centroid_lon,
                rc.{ccol('centroid_lat')} as centroid_lat
            FROM {tendency_table} nt
            LEFT JOIN {centroids_table} rc ON rc.{ccol('region_level')} = 'township' AND rc.{ccol('region_name')} = nt.{tcol('region')}
            WHERE nt.{tcol('level')} = 'township'
        """
        params = []

        # 过滤条件
        if city is not None:
            query += f" AND nt.{tcol('city')} = ?"
            params.append(city)
        if county is not None:
            query += f" AND nt.{tcol('county')} = ?"
            params.append(county)
        elif city is not None:
            # Handle 东莞市/中山市 (no county level)
            query += f" AND (nt.{tcol('county')} IS NULL OR nt.{tcol('county')} = '')"
        if township is not None:
            query += f" AND nt.{tcol('township')} = ?"
            params.append(township)
        if region_name is not None:
            query += f" AND nt.{tcol('region')} = ?"
            params.append(region_name)
        if ngram is not None:
            query += f" AND nt.{tcol('ngram')} = ?"
            params.append(ngram)
        if min_tendency is not None:
            query += f" AND nt.{tcol('lift')} >= ?"
            params.append(min_tendency)

        query += f"""
            ORDER BY nt.{tcol('lift')} DESC
            LIMIT ?
        """
        params.append(limit)

    elif region_level == "county":
        # County 级别：从 township 聚合
        regional_total_raw_sum = f"SUM(nt.{tcol('regional_total_raw')})" if has_regional_total_raw else "NULL"

        # 使用 regional_total_raw 计算 Lift（如果存在），否则使用 regional_total
        if has_regional_total_raw:
            lift_formula = f"""(SUM(nt.{tcol('regional_count')}) * 1.0 / SUM(nt.{tcol('regional_total_raw')})) /
                (SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}))"""
        else:
            lift_formula = f"""(SUM(nt.{tcol('regional_count')}) * 1.0 / SUM(nt.{tcol('regional_total')})) /
                (SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}))"""

        query = f"""
            SELECT
                'county' as region_level,
                nt.{tcol('county')} as region_name,
                nt.{tcol('city')} as city,
                nt.{tcol('county')} as county,
                NULL as township,
                nt.{tcol('ngram')} as ngram,
                nt.{tcol('n')} as n,
                nt.{tcol('position')} as position,
                {lift_formula} as tendency_score,
                CASE
                    WHEN SUM(nt.{tcol('regional_total')}) - SUM(nt.{tcol('regional_count')}) + 1 > 0 AND
                         SUM(nt.{tcol('global_total')}) - SUM(nt.{tcol('global_count')}) + 1 > 0
                    THEN LOG((SUM(nt.{tcol('regional_count')}) * 1.0 / (SUM(nt.{tcol('regional_total')}) - SUM(nt.{tcol('regional_count')}) + 1)) /
                             (SUM(nt.{tcol('global_count')}) * 1.0 / (SUM(nt.{tcol('global_total')}) - SUM(nt.{tcol('global_count')}) + 1)))
                    ELSE 0.0
                END as log_odds,
                CASE
                    WHEN SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}) > 0
                    THEN (SUM(nt.{tcol('regional_count')}) - SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')})) /
                         SQRT(SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}) *
                              (1 - SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')})))
                    ELSE 0.0
                END as z_score,
                SUM(nt.{tcol('regional_count')}) as frequency,
                SUM(nt.{tcol('regional_total')}) as regional_total,
                {regional_total_raw_sum} as regional_total_raw,
                SUM(nt.{tcol('global_count')}) as expected_frequency,
                SUM(nt.{tcol('global_total')}) as global_total,
                rc.{ccol('centroid_lon')} as centroid_lon,
                rc.{ccol('centroid_lat')} as centroid_lat
            FROM {tendency_table} nt
            LEFT JOIN {centroids_table} rc ON rc.{ccol('region_level')} = 'county' AND rc.{ccol('region_name')} = nt.{tcol('county')}
            WHERE nt.{tcol('level')} = 'township'
        """
        params = []

        # 过滤条件
        if city is not None:
            query += f" AND nt.{tcol('city')} = ?"
            params.append(city)
        if county is not None:
            query += f" AND nt.{tcol('county')} = ?"
            params.append(county)
        if region_name is not None:
            query += f" AND nt.{tcol('county')} = ?"
            params.append(region_name)
        if ngram is not None:
            query += f" AND nt.{tcol('ngram')} = ?"
            params.append(ngram)

        query += f"""
            GROUP BY nt.{tcol('county')}, nt.{tcol('city')}, nt.{tcol('ngram')}, nt.{tcol('n')}, nt.{tcol('position')}
        """

        # min_tendency 过滤需要在 HAVING 子句中
        if min_tendency is not None:
            query += " HAVING tendency_score >= ?"
            params.append(min_tendency)

        query += " ORDER BY tendency_score DESC LIMIT ?"
        params.append(limit)

    else:  # region_level == "city"
        # City 级别：从 township 聚合
        regional_total_raw_sum = f"SUM(nt.{tcol('regional_total_raw')})" if has_regional_total_raw else "NULL"

        # 使用 regional_total_raw 计算 Lift（如果存在），否则使用 regional_total
        if has_regional_total_raw:
            lift_formula = f"""(SUM(nt.{tcol('regional_count')}) * 1.0 / SUM(nt.{tcol('regional_total_raw')})) /
                (SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}))"""
        else:
            lift_formula = f"""(SUM(nt.{tcol('regional_count')}) * 1.0 / SUM(nt.{tcol('regional_total')})) /
                (SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}))"""

        query = f"""
            SELECT
                'city' as region_level,
                nt.{tcol('city')} as region_name,
                nt.{tcol('city')} as city,
                NULL as county,
                NULL as township,
                nt.{tcol('ngram')} as ngram,
                nt.{tcol('n')} as n,
                nt.{tcol('position')} as position,
                {lift_formula} as tendency_score,
                CASE
                    WHEN SUM(nt.{tcol('regional_total')}) - SUM(nt.{tcol('regional_count')}) + 1 > 0 AND
                         SUM(nt.{tcol('global_total')}) - SUM(nt.{tcol('global_count')}) + 1 > 0
                    THEN LOG((SUM(nt.{tcol('regional_count')}) * 1.0 / (SUM(nt.{tcol('regional_total')}) - SUM(nt.{tcol('regional_count')}) + 1)) /
                             (SUM(nt.{tcol('global_count')}) * 1.0 / (SUM(nt.{tcol('global_total')}) - SUM(nt.{tcol('global_count')}) + 1)))
                    ELSE 0.0
                END as log_odds,
                CASE
                    WHEN SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}) > 0
                    THEN (SUM(nt.{tcol('regional_count')}) - SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')})) /
                         SQRT(SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}) *
                              (1 - SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')})))
                    ELSE 0.0
                END as z_score,
                SUM(nt.{tcol('regional_count')}) as frequency,
                SUM(nt.{tcol('regional_total')}) as regional_total,
                {regional_total_raw_sum} as regional_total_raw,
                SUM(nt.{tcol('global_count')}) as expected_frequency,
                SUM(nt.{tcol('global_total')}) as global_total,
                rc.{ccol('centroid_lon')} as centroid_lon,
                rc.{ccol('centroid_lat')} as centroid_lat
            FROM {tendency_table} nt
            LEFT JOIN {centroids_table} rc ON rc.{ccol('region_level')} = 'city' AND rc.{ccol('region_name')} = nt.{tcol('city')}
            WHERE nt.{tcol('level')} = 'township'
        """
        params = []

        # 过滤条件
        if city is not None:
            query += f" AND nt.{tcol('city')} = ?"
            params.append(city)
        if region_name is not None:
            query += f" AND nt.{tcol('city')} = ?"
            params.append(region_name)
        if ngram is not None:
            query += f" AND nt.{tcol('ngram')} = ?"
            params.append(ngram)

        query += f"""
            GROUP BY nt.{tcol('city')}, nt.{tcol('ngram')}, nt.{tcol('n')}, nt.{tcol('position')}
        """

        # min_tendency 过滤需要在 HAVING 子句中
        if min_tendency is not None:
            query += " HAVING tendency_score >= ?"
            params.append(min_tendency)

        query += " ORDER BY tendency_score DESC LIMIT ?"
        params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        # 提供更友好的错误信息
        if ngram and len(ngram) == 1:
            detail = f"No data found for single character '{ngram}'. Only n-grams (2-4 chars) are supported. Try using character tendency endpoints instead."
        else:
            detail = "No n-gram tendency data found with the given filters."

        raise HTTPException(status_code=404, detail=detail)

    return results


@router.get("/significance")
def get_ngram_significance(
    ngram: Optional[str] = Query(None, description="N-gram"),
    region_level: str = Query("county", description="区域级别"),
    region_name: Optional[str] = Query(None, description="区域名称"),
    city: Optional[str] = Query(None, description="城市"),
    county: Optional[str] = Query(None, description="区县"),
    is_significant: Optional[bool] = Query(None, description="仅显示显著结果"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取N-gram显著性（支持动态聚合）
    Get n-gram significance test results with dynamic aggregation

    - township: 直接查询 Township 级别数据
    - county: 从 Township 聚合到 County 级别
    - city: 从 Township 聚合到 City 级别
    """
    significance_table, scol = _ngram_schema(dbpath, T.NGRAM_SIGNIFICANCE)
    tendency_table, tcol = _ngram_schema(dbpath, T.NGRAM_TENDENCY)

    if region_level == "township":
        # Township 级别：直接查询
        query = f"""
            SELECT
                {scol("level")} as region_level,
                {scol("region")} as region_name,
                {scol("city")} as city,
                {scol("county")} as county,
                {scol("township")} as township,
                {scol("ngram")} as ngram,
                {scol("n")} as n,
                {scol("position")} as position,
                {scol("chi2")} as z_score,
                {scol("p_value")} as p_value,
                {scol("is_significant")} as is_significant,
                {scol("cramers_v")} as lift
            FROM {significance_table}
            WHERE {scol("level")} = 'township'
        """
        params = []

        if city is not None:
            query += f" AND {scol('city')} = ?"
            params.append(city)
        if county is not None:
            query += f" AND {scol('county')} = ?"
            params.append(county)
        if region_name is not None:
            query += f" AND {scol('region')} = ?"
            params.append(region_name)
        if ngram is not None:
            query += f" AND {scol('ngram')} = ?"
            params.append(ngram)
        if is_significant is not None:
            query += f" AND {scol('is_significant')} = ?"
            params.append(1 if is_significant else 0)

        query += f" ORDER BY ABS({scol('chi2')}) DESC LIMIT ?"
        params.append(limit)

    elif region_level == "county":
        # County 级别：从 Township 聚合
        # 使用 ngram_tendency 表的底层计数数据来重新计算 chi2
        query = f"""
            WITH chi2_calc AS (
                SELECT
                    nt.{tcol('county')} as county,
                    nt.{tcol('city')} as city,
                    nt.{tcol('ngram')} as ngram,
                    nt.{tcol('n')} as n,
                    nt.{tcol('position')} as position,
                    CASE
                        WHEN SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}) > 0
                        THEN POWER(SUM(nt.{tcol('regional_count')}) - SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}), 2) /
                             (SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}))
                        ELSE 0.0
                    END as chi2_value,
                    SUM(nt.{tcol('regional_total')}) as total
                FROM {tendency_table} nt
                WHERE nt.{tcol('level')} = 'township'
        """
        params = []

        if city is not None:
            query += f" AND nt.{tcol('city')} = ?"
            params.append(city)
        if county is not None:
            query += f" AND nt.{tcol('county')} = ?"
            params.append(county)
        if region_name is not None:
            query += f" AND nt.{tcol('county')} = ?"
            params.append(region_name)
        if ngram is not None:
            query += f" AND nt.{tcol('ngram')} = ?"
            params.append(ngram)

        query += f"""
                GROUP BY nt.{tcol('county')}, nt.{tcol('city')}, nt.{tcol('ngram')}, nt.{tcol('n')}, nt.{tcol('position')}
            )
            SELECT
                'county' as region_level,
                county as region_name,
                city,
                county,
                NULL as township,
                ngram,
                n,
                position,
                chi2_value as z_score,
                CASE
                    WHEN chi2_value > 0
                    THEN EXP(-chi2_value / 2.0) * SQRT(2.0 / (3.14159265359 * chi2_value))
                    ELSE 1.0
                END as p_value,
                CASE
                    WHEN chi2_value > 3.841
                    THEN 1
                    ELSE 0
                END as is_significant,
                CASE
                    WHEN total > 0
                    THEN SQRT(chi2_value) / total
                    ELSE 0.0
                END as lift
            FROM chi2_calc
        """

        if is_significant is not None:
            if is_significant:
                query += " WHERE chi2_value > 3.841"
            else:
                query += " WHERE chi2_value <= 3.841"

        query += " ORDER BY ABS(chi2_value) DESC LIMIT ?"
        params.append(limit)

    else:  # region_level == "city"
        # City 级别：从 Township 聚合
        query = f"""
            WITH chi2_calc AS (
                SELECT
                    nt.{tcol('city')} as city,
                    nt.{tcol('ngram')} as ngram,
                    nt.{tcol('n')} as n,
                    nt.{tcol('position')} as position,
                    CASE
                        WHEN SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}) > 0
                        THEN POWER(SUM(nt.{tcol('regional_count')}) - SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}), 2) /
                             (SUM(nt.{tcol('regional_total')}) * SUM(nt.{tcol('global_count')}) * 1.0 / SUM(nt.{tcol('global_total')}))
                        ELSE 0.0
                    END as chi2_value,
                    SUM(nt.{tcol('regional_total')}) as total
                FROM {tendency_table} nt
                WHERE nt.{tcol('level')} = 'township'
        """
        params = []

        if city is not None:
            query += f" AND nt.{tcol('city')} = ?"
            params.append(city)
        if region_name is not None:
            query += f" AND nt.{tcol('city')} = ?"
            params.append(region_name)
        if ngram is not None:
            query += f" AND nt.{tcol('ngram')} = ?"
            params.append(ngram)

        query += f"""
                GROUP BY nt.{tcol('city')}, nt.{tcol('ngram')}, nt.{tcol('n')}, nt.{tcol('position')}
            )
            SELECT
                'city' as region_level,
                city as region_name,
                city,
                NULL as county,
                NULL as township,
                ngram,
                n,
                position,
                chi2_value as z_score,
                CASE
                    WHEN chi2_value > 0
                    THEN EXP(-chi2_value / 2.0) * SQRT(2.0 / (3.14159265359 * chi2_value))
                    ELSE 1.0
                END as p_value,
                CASE
                    WHEN chi2_value > 3.841
                    THEN 1
                    ELSE 0
                END as is_significant,
                CASE
                    WHEN total > 0
                    THEN SQRT(chi2_value) / total
                    ELSE 0.0
                END as lift
            FROM chi2_calc
        """

        if is_significant is not None:
            if is_significant:
                query += " WHERE chi2_value > 3.841"
            else:
                query += " WHERE chi2_value <= 3.841"

        query += " ORDER BY ABS(chi2_value) DESC LIMIT ?"
        params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No n-gram significance data found"
        )

    return results
