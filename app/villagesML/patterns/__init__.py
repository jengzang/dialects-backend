"""
模式分析API
Pattern Analysis API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query, execute_single
from ..schema_runtime import qcolumn, qtable, normalize_region_level
from ..schema_keys import T

router = APIRouter(prefix="/patterns")


def _pattern_schema(dbpath: str, logical_table: str):
    return qtable(dbpath, logical_table), lambda name: qcolumn(dbpath, logical_table, name)


@router.get("/frequency/global")
def get_global_pattern_frequency(
    pattern_type: Optional[str] = Query(None, description="模式类型"),
    min_frequency: Optional[float] = Query(None, ge=0, le=1, description="最小频率（0-1之间的小数，如0.05表示5%）"),
    top_k: int = Query(100, ge=1, le=1000, description="返回Top K"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取全局模式频率
    Get global pattern frequencies

    Args:
        pattern_type: 模式类型（prefix/suffix/infix）
        min_frequency: 最小频率
        top_k: 返回Top K

    Returns:
        List[dict]: 模式频率列表
    """
    table, col = _pattern_schema(dbpath, T.PATTERN_FREQUENCY_GLOBAL)
    query = f"""
        SELECT
            {col("pattern")} as pattern,
            {col("pattern_type")} as pattern_type,
            {col("frequency")} as frequency,
            {col("village_count")} as village_count,
            {col("rank")} as rank
        FROM {table}
        WHERE 1=1
    """
    params = []

    if pattern_type is not None:
        query += f" AND {col('pattern_type')} = ?"
        params.append(pattern_type)

    if min_frequency is not None:
        query += f" AND {col('frequency')} >= ?"
        params.append(min_frequency)

    query += f" ORDER BY {col('frequency')} DESC LIMIT ?"
    params.append(top_k)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No patterns found"
        )

    return results


@router.get("/frequency/regional")
def get_regional_pattern_frequency(
    region_level: str = Query(..., description="区域级别"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    pattern_type: Optional[str] = Query(None, description="模式类型"),
    top_k: int = Query(50, ge=1, le=500, description="返回Top K"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取区域模式频率
    Get regional pattern frequencies

    Args:
        region_level: 区域级别（city/county/town）
        region_name: 区域名称（模糊匹配，可选，向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        pattern_type: 模式类型（可选）
        top_k: 返回Top K

    Returns:
        List[dict]: 区域模式频率列表
    """
    table, col = _pattern_schema(dbpath, T.PATTERN_REGIONAL_ANALYSIS)
    query = f"""
        SELECT DISTINCT
            {col("region_level")} as region_level,
            {col("region_name")} as region_name,
            {col("city")} as city,
            {col("county")} as county,
            {col("township")} as township,
            {col("pattern")} as pattern,
            {col("pattern_type")} as pattern_type,
            {col("frequency")} as frequency,
            {col("rank_within_region")} as rank_in_region
        FROM {table}
        WHERE {col("region_level")} = ?
    """
    params = [normalize_region_level(dbpath, T.PATTERN_REGIONAL_ANALYSIS, region_level)]

    # 优先使用层级参数（精确匹配）
    if city is not None:
        query += f" AND {col('city')} = ?"
        params.append(city)
    if county is not None:
        query += f" AND {col('county')} = ?"
        params.append(county)
    elif city is not None and region_level == 'township':
        # Handle 东莞市/中山市 (no county level)
        query += f" AND ({col('county')} IS NULL OR {col('county')} = '')"
    if township is not None:
        query += f" AND {col('township')} = ?"
        params.append(township)

    # 向后兼容：region_name（模糊匹配）
    if region_name is not None:
        query += f" AND ({col('city')} = ? OR {col('county')} = ? OR {col('township')} = ?)"
        params.extend([region_name, region_name, region_name])

    if pattern_type is not None:
        query += f" AND {col('pattern_type')} = ?"
        params.append(pattern_type)

    query += f" ORDER BY {col('frequency')} DESC LIMIT ?"
    params.append(top_k)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No patterns found for region_level: {region_level}"
        )

    return results


@router.get("/tendency")
def get_pattern_tendency(
    pattern: Optional[str] = Query(None, description="模式"),
    region_level: str = Query("county", description="区域级别"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    min_tendency: Optional[float] = Query(None, description="最小倾向值"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取模式倾向性
    Get pattern tendency scores

    Args:
        pattern: 模式（可选）
        region_level: 区域级别
        region_name: 区域名称（模糊匹配，可选，向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        min_tendency: 最小倾向值
        limit: 返回记录数

    Returns:
        List[dict]: 模式倾向性列表
    """
    table, col = _pattern_schema(dbpath, T.PATTERN_REGIONAL_ANALYSIS)
    query = f"""
        SELECT DISTINCT
            {col("region_level")} as region_level,
            {col("region_name")} as region_name,
            {col("city")} as city,
            {col("county")} as county,
            {col("township")} as township,
            {col("pattern")} as pattern,
            {col("pattern_type")} as pattern_type,
            {col("lift")} as tendency_score,
            {col("frequency")} as frequency,
            {col("global_frequency")} as global_frequency
        FROM {table}
        WHERE {col("region_level")} = ?
    """
    params = [normalize_region_level(dbpath, T.PATTERN_REGIONAL_ANALYSIS, region_level)]

    # 优先使用层级参数（精确匹配）
    if city is not None:
        query += f" AND {col('city')} = ?"
        params.append(city)
    if county is not None:
        query += f" AND {col('county')} = ?"
        params.append(county)
    elif city is not None and region_level == 'township':
        # Handle 东莞市/中山市 (no county level)
        query += f" AND ({col('county')} IS NULL OR {col('county')} = '')"
    if township is not None:
        query += f" AND {col('township')} = ?"
        params.append(township)

    # 向后兼容：region_name（模糊匹配）
    if region_name is not None:
        query += f" AND ({col('city')} = ? OR {col('county')} = ? OR {col('township')} = ?)"
        params.extend([region_name, region_name, region_name])

    if pattern is not None:
        query += f" AND {col('pattern')} = ?"
        params.append(pattern)

    if min_tendency is not None:
        query += f" AND {col('lift')} >= ?"
        params.append(min_tendency)

    query += f" ORDER BY {col('lift')} DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No pattern tendency data found"
        )

    return results


@router.get("/structural")
def get_structural_patterns(
    pattern_type: Optional[str] = Query(None, description="模式类型"),
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频率"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取结构化模式
    Get structural naming patterns

    Args:
        pattern_type: 模式类型（可选）
        min_frequency: 最小频率（可选）

    Returns:
        List[dict]: 结构化模式列表
    """
    table, col = _pattern_schema(dbpath, T.STRUCTURAL_PATTERNS)
    query = f"""
        SELECT DISTINCT
            {col("pattern")} as pattern,
            {col("pattern_type")} as pattern_type,
            {col("n")} as n,
            {col("position")} as position,
            {col("frequency")} as frequency,
            {col("example")} as example,
            {col("description")} as description
        FROM {table}
        WHERE 1=1
    """
    params = []

    if pattern_type is not None:
        query += f" AND {col('pattern_type')} = ?"
        params.append(pattern_type)

    if min_frequency is not None:
        query += f" AND {col('frequency')} >= ?"
        params.append(min_frequency)

    query += f" ORDER BY {col('frequency')} DESC"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No structural patterns found"
        )

    return results
