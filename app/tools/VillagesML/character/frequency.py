"""
字符频率API
Character Frequency API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query
from ..config import DEFAULT_RUN_ID, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from ..models import CharFrequency, RegionalCharFrequency

router = APIRouter(prefix="/character/frequency", tags=["character"])


@router.get("/global", response_model=List[CharFrequency])
def get_global_character_frequency(
    run_id: str = Query(DEFAULT_RUN_ID, description="分析运行ID"),
    top_n: int = Query(100, ge=1, le=1000, description="返回前N个字符"),
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频次过滤"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取全局字符频率
    Get global character frequency statistics

    Args:
        run_id: 分析运行ID
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
        WHERE run_id = ?
    """
    params = [run_id]

    # 现场过滤：最小频次
    if min_frequency is not None:
        query += " AND frequency >= ?"
        params.append(min_frequency)

    # 现场排序和限制
    query += " ORDER BY frequency DESC LIMIT ?"
    params.append(top_n)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(status_code=404, detail=f"No data found for run_id: {run_id}")

    return results


@router.get("/regional", response_model=List[RegionalCharFrequency])
def get_regional_character_frequency(
    run_id: str = Query(DEFAULT_RUN_ID, description="分析运行ID"),
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称（不指定返回所有区域）"),
    top_n: int = Query(50, ge=1, le=500, description="每个区域返回前N个字符"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取区域字符频率
    Get regional character frequency statistics

    Args:
        run_id: 分析运行ID
        region_level: 区域级别 (city/county/township)
        region_name: 区域名称（可选）
        top_n: 每个区域返回前N个字符

    Returns:
        List[RegionalCharFrequency]: 区域字符频率列表
    """
    # 构建查询
    query = """
        SELECT
            region_name,
            char as character,
            frequency,
            rank_within_region as rank
        FROM char_frequency_regional
        WHERE run_id = ? AND region_level = ?
    """
    params = [run_id, region_level]

    # 现场过滤：区域名称
    if region_name is not None:
        query += " AND region_name = ?"
        params.append(region_name)

    # 现场排序和限制（每个区域前N个）
    query += " AND rank_within_region <= ? ORDER BY region_name, rank_within_region"
    params.append(top_n)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for run_id: {run_id}, region_level: {region_level}"
        )

    return results
