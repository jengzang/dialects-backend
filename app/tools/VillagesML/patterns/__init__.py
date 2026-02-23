"""
模式分析API
Pattern Analysis API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/patterns", tags=["pattern-analysis"])


@router.get("/frequency/global")
def get_global_pattern_frequency(
    pattern_type: Optional[str] = Query(None, description="模式类型"),
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频率"),
    top_k: int = Query(100, ge=1, le=1000, description="返回Top K"),
    db: sqlite3.Connection = Depends(get_db)
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
    query = """
        SELECT
            pattern,
            pattern_type,
            frequency,
            village_count,
            rank
        FROM pattern_frequency_global
        WHERE 1=1
    """
    params = []

    if pattern_type is not None:
        query += " AND pattern_type = ?"
        params.append(pattern_type)

    if min_frequency is not None:
        query += " AND frequency >= ?"
        params.append(min_frequency)

    query += " ORDER BY frequency DESC LIMIT ?"
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
    region_name: Optional[str] = Query(None, description="区域名称"),
    pattern_type: Optional[str] = Query(None, description="模式类型"),
    top_k: int = Query(50, ge=1, le=500, description="返回Top K"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取区域模式频率
    Get regional pattern frequencies

    Args:
        region_level: 区域级别（city/county/town）
        region_name: 区域名称（可选）
        pattern_type: 模式类型（可选）
        top_k: 返回Top K

    Returns:
        List[dict]: 区域模式频率列表
    """
    query = """
        SELECT
            region_level,
            region_name,
            pattern,
            pattern_type,
            frequency,
            rank_within_region as rank_in_region
        FROM pattern_frequency_regional
        WHERE region_level = ?
    """
    params = [region_level]

    if region_name is not None:
        query += " AND region_name = ?"
        params.append(region_name)

    if pattern_type is not None:
        query += " AND pattern_type = ?"
        params.append(pattern_type)

    query += " ORDER BY frequency DESC LIMIT ?"
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
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    pattern: Optional[str] = Query(None, description="模式"),
    region_level: str = Query("county", description="区域级别"),
    min_tendency: Optional[float] = Query(None, description="最小倾向值"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取模式倾向性
    Get pattern tendency scores

    Args:
        pattern: 模式（可选）
        region_level: 区域级别
        min_tendency: 最小倾向值
        limit: 返回记录数

    Returns:
        List[dict]: 模式倾向性列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("patterns")

    query = """
        SELECT
            region_level,
            region_name,
            pattern,
            pattern_type,
            lift as tendency_score,
            frequency,
            global_frequency
        FROM pattern_tendency
        WHERE run_id = ? AND region_level = ?
    """
    params = [run_id, region_level]

    if pattern is not None:
        query += " AND pattern = ?"
        params.append(pattern)

    if min_tendency is not None:
        query += " AND tendency_score >= ?"
        params.append(min_tendency)

    query += " ORDER BY tendency_score DESC LIMIT ?"
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
    db: sqlite3.Connection = Depends(get_db)
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
    query = """
        SELECT
            pattern,
            pattern_type,
            n,
            position,
            frequency,
            example,
            description
        FROM structural_patterns
        WHERE 1=1
    """
    params = []

    if pattern_type is not None:
        query += " AND pattern_type = ?"
        params.append(pattern_type)

    if min_frequency is not None:
        query += " AND frequency >= ?"
        params.append(min_frequency)

    query += " ORDER BY frequency DESC"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No structural patterns found"
        )

    return results
