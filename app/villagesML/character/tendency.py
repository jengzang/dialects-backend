"""
字符倾向性API
Character Tendency API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query
from ..models import CharTendency, CharTendencyByRegion
from ..schema_runtime import qcolumn, qtable, normalize_region_level
from ..schema_keys import C, T

router = APIRouter(prefix="/character/tendency")


@router.get("/by-region", response_model=List[CharTendency])
def get_character_tendency_by_region(
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    top_n: int = Query(50, ge=1, le=500, description="返回前N个字符"),
    sort_by: str = Query("z_score", description="排序字段", pattern="^(z_score|lift|log_odds)$"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取指定区域的字符倾向性
    Get character tendency for a specific region

    Args:
        region_level: 区域级别 (city/county/township)
        region_name: 区域名称（模糊匹配，可选，向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        top_n: 返回前N个高倾向字符
        sort_by: 排序字段 (z_score/lift/log_odds)

    Returns:
        List[CharTendency]: 字符倾向性列表
    """
    table = qtable(dbpath, T.CHAR_REGIONAL_ANALYSIS)
    region_level_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)
    region_name_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)
    city_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CITY)
    county_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.COUNTY)
    township_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.TOWNSHIP)
    char_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CHAR)
    lift_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.LIFT)
    log_odds_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.LOG_ODDS)
    z_score_col = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.Z_SCORE)
    sort_col_map = {
        "z_score": z_score_col,
        "lift": lift_col,
        "log_odds": log_odds_col,
    }
    sort_col = sort_col_map[sort_by]

    query = f"""
        SELECT DISTINCT
            {region_level_col} as region_level,
            {region_name_col} as region_name,
            {city_col} as city,
            {county_col} as county,
            {township_col} as township,
            {char_col} as character,
            {lift_col} as lift,
            {log_odds_col} as log_odds,
            {z_score_col} as z_score,
            ROW_NUMBER() OVER (ORDER BY {sort_col} DESC) as rank
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

    query += f" ORDER BY {sort_col} DESC LIMIT ?"
    params.append(top_n)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for specified region"
        )

    return results


@router.get("/by-char", response_model=List[CharTendencyByRegion])
def get_character_tendency_by_char(
    character: str = Query(..., description="字符", min_length=1, max_length=1),
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取指定字符在各区域的倾向性
    Get tendency of a specific character across regions

    Args:
        character: 字符
        region_level: 区域级别 (city/county/township)
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）

    Returns:
        List[CharTendencyByRegion]: 各区域倾向性列表（包含区域中心点坐标）
    """
    regional_table = qtable(dbpath, T.CHAR_REGIONAL_ANALYSIS)
    regional_region_level = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)
    regional_region_name = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)
    regional_city = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CITY)
    regional_county = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.COUNTY)
    regional_township = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.TOWNSHIP)
    regional_char = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.CHAR)
    regional_lift = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.LIFT)
    regional_z_score = qcolumn(dbpath, T.CHAR_REGIONAL_ANALYSIS, C.CHAR_REGIONAL_ANALYSIS.Z_SCORE)
    villages_table = qtable(dbpath, T.VILLAGES)
    villages_longitude = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.LONGITUDE)
    villages_latitude = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.LATITUDE)
    coord_field_map = {
        "city": qcolumn(dbpath, T.VILLAGES, C.VILLAGES.CITY),
        "county": qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COUNTY),
        "township": qcolumn(dbpath, T.VILLAGES, C.VILLAGES.TOWNSHIP),
    }
    coord_field = coord_field_map[region_level]

    query = f"""
        SELECT
            c.{regional_region_level} as region_level,
            c.{regional_region_name} as region_name,
            c.{regional_city} as city,
            c.{regional_county} as county,
            c.{regional_township} as township,
            c.{regional_lift} as lift,
            c.{regional_z_score} as z_score,
            AVG(v.{villages_longitude}) as centroid_lon,
            AVG(v.{villages_latitude}) as centroid_lat
        FROM {regional_table} c
        LEFT JOIN {villages_table} v ON c.{regional_region_name} = v.{coord_field}
        WHERE c.{regional_char} = ? AND c.{regional_region_level} = ?
    """
    params = [character, normalize_region_level(dbpath, T.CHAR_REGIONAL_ANALYSIS, region_level)]

    # 优先使用层级参数（精确匹配）
    if city is not None:
        query += f" AND c.{regional_city} = ?"
        params.append(city)
    if county is not None:
        query += f" AND c.{regional_county} = ?"
        params.append(county)
    if township is not None:
        query += f" AND c.{regional_township} = ?"
        params.append(township)

    query += f"""
        GROUP BY c.{regional_region_level}, c.{regional_region_name}, c.{regional_city}, c.{regional_county}, c.{regional_township}, c.{regional_lift}, c.{regional_z_score}
        ORDER BY c.{regional_z_score} DESC
    """

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for character: {character}"
        )

    return results
