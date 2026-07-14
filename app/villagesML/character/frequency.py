"""
字符频率API
Character Frequency API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query
from ..models import CharFrequency, RegionalCharFrequency
from ..schema_runtime import qcolumn, qtable, normalize_region_level
from ..schema_keys import C, T

router = APIRouter(prefix="/character/frequency")


@router.get("/global", response_model=List[CharFrequency])
def get_global_character_frequency(
    top_n: int = Query(100, ge=1, le=1000, description="返回前N个字符"),
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频次过滤"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取全局字符频率
    Get global character frequency statistics

    Args:
        top_n: 返回前N个高频字符
        min_frequency: 最小频次阈值（现场过滤）

    Returns:
        List[CharFrequency]: 字符频率列表
    """
    table = qtable(dbpath, T.CHAR_FREQUENCY_GLOBAL)
    char_col = qcolumn(dbpath, T.CHAR_FREQUENCY_GLOBAL, C.CHAR_FREQUENCY_GLOBAL.CHAR)
    frequency_col = qcolumn(dbpath, T.CHAR_FREQUENCY_GLOBAL, C.CHAR_FREQUENCY_GLOBAL.FREQUENCY)
    village_count_col = qcolumn(dbpath, T.CHAR_FREQUENCY_GLOBAL, C.CHAR_FREQUENCY_GLOBAL.VILLAGE_COUNT)
    rank_col = qcolumn(dbpath, T.CHAR_FREQUENCY_GLOBAL, C.CHAR_FREQUENCY_GLOBAL.RANK)

    query = f"""
        SELECT
            {char_col} as character,
            {frequency_col} as frequency,
            {village_count_col} as village_count,
            {rank_col} as rank
        FROM {table}
        WHERE 1=1
    """
    params = []

    # 现场过滤：最小频次
    if min_frequency is not None:
        query += f" AND {frequency_col} >= ?"
        params.append(min_frequency)

    # 现场排序和限制
    query += f" ORDER BY {frequency_col} DESC LIMIT ?"
    params.append(top_n)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(status_code=404, detail="No data found")

    return results


@router.get("/regional", response_model=List[RegionalCharFrequency])
def get_regional_character_frequency(
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    top_n: int = Query(50, ge=1, le=500, description="每个区域返回前N个字符"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取区域字符频率
    Get regional character frequency statistics

    Args:
        region_level: 区域级别 (city/county/township)
        region_name: 区域名称（模糊匹配，可选，向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        top_n: 每个区域返回前N个字符

    Returns:
        List[RegionalCharFrequency]: 区域字符频率列表
    """
    # 构建查询
    table = qtable(dbpath, T.CHAR_REGIONAL_ANALYSIS)
    region_level_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)
    region_name_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)
    city_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CITY)
    county_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.COUNTY)
    township_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.TOWNSHIP)
    char_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CHAR)
    frequency_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.FREQUENCY)
    village_count_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.VILLAGE_COUNT)
    rank_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.RANK_WITHIN_REGION)

    query = f"""
        SELECT DISTINCT
            {region_level_col} as region_level,
            {region_name_col} as region_name,
            {city_col} as city,
            {county_col} as county,
            {township_col} as township,
            {char_col} as character,
            {frequency_col} as frequency,
            {village_count_col} as village_count,
            {rank_col} as rank
        FROM {table}
        WHERE {region_level_col} = ?
    """
    params = [normalize_region_level(dbpath, T.CHAR_REGIONAL_ANALYSIS, region_level)]

    # 优先使用层级参数（精确匹配）
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

    # 向后兼容：region_name（模糊匹配）
    if region_name is not None:
        query += f" AND ({city_col} = ? OR {county_col} = ? OR {township_col} = ?)"
        params.extend([region_name, region_name, region_name])

    # 现场排序和限制（每个区域前N个）
    query += f" AND {rank_col} <= ? ORDER BY {region_name_col}, {rank_col}"
    params.append(top_n)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for region_level: {region_level}"
        )

    return results
