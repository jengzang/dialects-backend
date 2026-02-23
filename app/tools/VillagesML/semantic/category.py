"""
语义类别API
Semantic Category API endpoints
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.concurrency import run_in_threadpool
from typing import List, Optional
import sqlite3

from ..dependencies import get_db_connection, execute_query
from ..config import DEFAULT_RUN_ID, DEFAULT_SEMANTIC_RUN_ID
from ..models import SemanticCategory, SemanticVTF, RegionalSemanticVTF, SemanticTendency

router = APIRouter(prefix="/semantic/category", tags=["semantic"])


def _get_semantic_categories_sync():
    """同步获取所有语义类别"""
    with get_db_connection() as db:
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


@router.get("/list", response_model=List[SemanticCategory])
async def get_semantic_categories():
    """
    获取所有语义类别
    Get all semantic categories

    Returns:
        List[SemanticCategory]: 语义类别列表
    """
    return await run_in_threadpool(_get_semantic_categories_sync)


def _get_global_semantic_vtf_sync(run_id: str, category: Optional[str]):
    """同步获取全局语义虚拟词频"""
    with get_db_connection() as db:
        query = """
            SELECT
                category,
                vtf,
                character_count
            FROM semantic_vtf_global
            WHERE run_id = ?
        """
        params = [run_id]

        if category is not None:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY vtf DESC"
        results = execute_query(db, query, tuple(params))

        if not results:
            raise HTTPException(status_code=404, detail=f"No VTF data found for run_id: {run_id}")
        return results


@router.get("/vtf/global", response_model=List[SemanticVTF])
async def get_global_semantic_vtf(
    run_id: str = Query(DEFAULT_SEMANTIC_RUN_ID, description="分析运行ID"),
    category: Optional[str] = Query(None, description="语义类别过滤")
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
    return await run_in_threadpool(_get_global_semantic_vtf_sync, run_id, category)


def _get_regional_semantic_vtf_sync(run_id: str, region_level: str, region_name: Optional[str], category: Optional[str]):
    """同步获取区域语义虚拟词频"""
    with get_db_connection() as db:
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

        if region_name is not None:
            query += " AND region_name = ?"
            params.append(region_name)

        if category is not None:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY region_name, vtf DESC"
        results = execute_query(db, query, tuple(params))

        if not results:
            raise HTTPException(status_code=404, detail=f"No regional VTF data found")
        return results


@router.get("/vtf/regional", response_model=List[RegionalSemanticVTF])
async def get_regional_semantic_vtf(
    run_id: str = Query(DEFAULT_SEMANTIC_RUN_ID, description="分析运行ID"),
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称"),
    category: Optional[str] = Query(None, description="语义类别")
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
    return await run_in_threadpool(_get_regional_semantic_vtf_sync, run_id, region_level, region_name, category)


def _get_semantic_tendency_sync(run_id: str, region_level: str, region_name: str, top_n: int):
    """同步获取区域语义倾向性"""
    with get_db_connection() as db:
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


@router.get("/tendency", response_model=List[SemanticTendency])
async def get_semantic_tendency(
    run_id: str = Query(DEFAULT_SEMANTIC_RUN_ID, description="分析运行ID"),
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: str = Query(..., description="区域名称"),
    top_n: int = Query(9, ge=1, le=20, description="返回前N个类别")
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
    return await run_in_threadpool(_get_semantic_tendency_sync, run_id, region_level, region_name, top_n)
