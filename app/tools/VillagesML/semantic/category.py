"""
语义类别API
Semantic Category API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query
from ..config import DEFAULT_RUN_ID, DEFAULT_SEMANTIC_RUN_ID
from ..models import SemanticCategory, SemanticVTF, RegionalSemanticVTF, SemanticTendency

router = APIRouter(prefix="/semantic/category", tags=["semantic"])


@router.get("/list", response_model=List[SemanticCategory])
def get_semantic_categories(db: sqlite3.Connection = Depends(get_db)):
    """
    获取所有语义类别
    Get all semantic categories

    Returns:
        List[SemanticCategory]: 语义类别列表
    """
    query = """
        SELECT
            category,
            category as description,
            vtf_count as character_count
        FROM semantic_vtf_global
        WHERE run_id = ?
        ORDER BY category
    """

    results = execute_query(db, query, (DEFAULT_SEMANTIC_RUN_ID,))

    if not results:
        raise HTTPException(status_code=404, detail="No semantic categories found")

    return results


@router.get("/vtf/global", response_model=List[SemanticVTF])
def get_global_semantic_vtf(
    run_id: str = Query(DEFAULT_SEMANTIC_RUN_ID, description="分析运行ID"),
    category: Optional[str] = Query(None, description="语义类别过滤"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取全局语义虚拟词频
    Get global semantic VTF (Virtual Term Frequency)

    Args:
        run_id: 分析运行ID
        category: 语义类别（可选）

    Returns:
        List[SemanticVTF]: 语义VTF列表
    """
    query = """
        SELECT
            category,
            vtf,
            character_count
        FROM semantic_vtf_global
        WHERE run_id = ?
    """
    params = [run_id]

    # 现场过滤：类别
    if category is not None:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY vtf DESC"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(status_code=404, detail=f"No VTF data found for run_id: {run_id}")

    return results


@router.get("/vtf/regional", response_model=List[RegionalSemanticVTF])
def get_regional_semantic_vtf(
    run_id: str = Query(DEFAULT_SEMANTIC_RUN_ID, description="分析运行ID"),
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称"),
    category: Optional[str] = Query(None, description="语义类别"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取区域语义虚拟词频
    Get regional semantic VTF

    Args:
        run_id: 分析运行ID
        region_level: 区域级别 (city/county/township)
        region_name: 区域名称（可选）
        category: 语义类别（可选）

    Returns:
        List[RegionalSemanticVTF]: 区域语义VTF列表
    """
    query = """
        SELECT
            region_name,
            category,
            vtf,
            intensity_index
        FROM semantic_vtf_regional
        WHERE run_id = ? AND region_level = ?
    """
    params = [run_id, region_level]

    # 现场过滤
    if region_name is not None:
        query += " AND region_name = ?"
        params.append(region_name)

    if category is not None:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY region_name, vtf DESC"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No regional VTF data found"
        )

    return results


@router.get("/tendency", response_model=List[SemanticTendency])
def get_semantic_tendency(
    run_id: str = Query(DEFAULT_SEMANTIC_RUN_ID, description="分析运行ID"),
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: str = Query(..., description="区域名称"),
    top_n: int = Query(9, ge=1, le=20, description="返回前N个类别"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取区域语义倾向性
    Get semantic tendency for a region

    Args:
        run_id: 分析运行ID
        region_level: 区域级别
        region_name: 区域名称
        top_n: 返回前N个类别

    Returns:
        List[SemanticTendency]: 语义倾向性列表
    """
    query = """
        SELECT
            category,
            lift,
            z_score
        FROM semantic_tendency
        WHERE run_id = ? AND region_level = ? AND region_name = ?
        ORDER BY z_score DESC
        LIMIT ?
    """

    results = execute_query(db, query, (run_id, region_level, region_name, top_n))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No semantic tendency data found for region: {region_name}"
        )

    return results
