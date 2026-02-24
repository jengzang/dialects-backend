"""
字符频率API
Character Frequency API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query
from ..models import CharFrequency, RegionalCharFrequency

router = APIRouter(prefix="/character/frequency")


@router.get("/global", response_model=List[CharFrequency])
def get_global_character_frequency(
    top_n: int = Query(100, ge=1, le=1000, description="返回前N个字符"),
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频次过滤"),
    db: sqlite3.Connection = Depends(get_db)
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
    query = """
        SELECT
            char as character,
            frequency,
            village_count,
            rank
        FROM char_frequency_global
        WHERE 1=1
    """
    params = []

    # 现场过滤：最小频次
    if min_frequency is not None:
        query += " AND frequency >= ?"
        params.append(min_frequency)

    # 现场排序和限制
    query += " ORDER BY frequency DESC LIMIT ?"
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
    db: sqlite3.Connection = Depends(get_db)
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
    query = """
        SELECT
            region_level,
            region_name,
            city,
            county,
            township,
            char as character,
            frequency,
            village_count,
            rank_within_region as rank
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

    # 现场排序和限制（每个区域前N个）
    query += " AND rank_within_region <= ? ORDER BY region_name, rank_within_region"
    params.append(top_n)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for region_level: {region_level}"
        )

    return results
