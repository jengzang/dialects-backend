"""
字符倾向性API
Character Tendency API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query
from ..models import CharTendency, CharTendencyByRegion

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
    db: sqlite3.Connection = Depends(get_db)
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
    query = f"""
        SELECT
            region_level,
            region_name,
            city,
            county,
            township,
            char as character,
            lift,
            log_odds,
            z_score,
            ROW_NUMBER() OVER (ORDER BY {sort_by} DESC) as rank
        FROM char_regional_analysis
        WHERE region_level = ?
    """
    params = [region_level]

    # 优先使用层级参数（精确匹配）
    if city is not None:
        query += " AND city = ?"
        params.append(city)
    if county is not None:
        query += " AND county = ?"
        params.append(county)
    if township is not None:
        query += " AND township = ?"
        params.append(township)

    # 向后兼容：region_name（模糊匹配）
    if region_name is not None:
        query += " AND (city = ? OR county = ? OR township = ?)"
        params.extend([region_name, region_name, region_name])

    query += f" ORDER BY {sort_by} DESC LIMIT ?"
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
    db: sqlite3.Connection = Depends(get_db)
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
    # 根据 region_level 确定坐标计算的字段
    if region_level == 'city':
        coord_field = '市级'
    elif region_level == 'county':
        coord_field = '区县级'
    else:  # township
        coord_field = '乡镇级'

    query = f"""
        SELECT
            c.region_level,
            c.region_name,
            c.city,
            c.county,
            c.township,
            c.lift,
            c.z_score,
            AVG(v.longitude) as centroid_lon,
            AVG(v.latitude) as centroid_lat
        FROM char_regional_analysis c
        LEFT JOIN 广东省自然村_预处理 v ON c.region_name = v.{coord_field}
        WHERE c.char = ? AND c.region_level = ?
    """
    params = [character, region_level]

    # 优先使用层级参数（精确匹配）
    if city is not None:
        query += " AND c.city = ?"
        params.append(city)
    if county is not None:
        query += " AND c.county = ?"
        params.append(county)
    if township is not None:
        query += " AND c.township = ?"
        params.append(township)

    query += """
        GROUP BY c.region_level, c.region_name, c.city, c.county, c.township, c.lift, c.z_score
        ORDER BY c.z_score DESC
    """

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for character: {character}"
        )

    return results
