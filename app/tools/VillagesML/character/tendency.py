"""
字符倾向性API
Character Tendency API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List
import sqlite3

from ..dependencies import get_db, execute_query
from ..config import DEFAULT_RUN_ID
from ..models import CharTendency, CharTendencyByRegion

router = APIRouter(prefix="/character/tendency", tags=["character"])


@router.get("/by-region", response_model=List[CharTendency])
def get_character_tendency_by_region(
    run_id: str = Query(DEFAULT_RUN_ID, description="分析运行ID"),
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: str = Query(..., description="区域名称"),
    top_n: int = Query(50, ge=1, le=500, description="返回前N个字符"),
    sort_by: str = Query("z_score", description="排序字段", pattern="^(z_score|lift|log_odds)$"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取指定区域的字符倾向性
    Get character tendency for a specific region

    Args:
        run_id: 分析运行ID
        region_level: 区域级别 (city/county/township)
        region_name: 区域名称
        top_n: 返回前N个高倾向字符
        sort_by: 排序字段 (z_score/lift/log_odds)

    Returns:
        List[CharTendency]: 字符倾向性列表
    """
    query = f"""
        SELECT
            char as character,
            lift,
            log_odds,
            z_score,
            ROW_NUMBER() OVER (ORDER BY {sort_by} DESC) as rank
        FROM regional_tendency
        WHERE run_id = ? AND region_level = ? AND region_name = ?
        ORDER BY {sort_by} DESC
        LIMIT ?
    """

    results = execute_query(db, query, (run_id, region_level, region_name, top_n))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for region: {region_name}"
        )

    return results


@router.get("/by-char", response_model=List[CharTendencyByRegion])
def get_character_tendency_by_char(
    run_id: str = Query(DEFAULT_RUN_ID, description="分析运行ID"),
    character: str = Query(..., description="字符", min_length=1, max_length=1),
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取指定字符在各区域的倾向性
    Get tendency of a specific character across regions

    Args:
        run_id: 分析运行ID
        character: 字符
        region_level: 区域级别 (city/county/township)

    Returns:
        List[CharTendencyByRegion]: 各区域倾向性列表
    """
    query = """
        SELECT
            region_name,
            lift,
            z_score
        FROM regional_tendency
        WHERE run_id = ? AND char = ? AND region_level = ?
        ORDER BY z_score DESC
    """

    results = execute_query(db, query, (run_id, character, region_level))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for character: {character}"
        )

    return results
