"""
空间-倾向性整合分析API
Spatial-Tendency Integration API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single
from ..config import DEFAULT_RUN_ID
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/spatial", tags=["spatial-integration"])


@router.get("/integration")
def get_spatial_tendency_integration(
    run_id: Optional[str] = Query(None, description="整合分析运行ID（留空使用活跃版本）"),
    character: Optional[str] = Query(None, description="字符过滤"),
    cluster_id: Optional[int] = Query(None, description="聚类ID过滤"),
    min_cluster_size: Optional[int] = Query(None, ge=1, description="最小聚类大小"),
    min_spatial_coherence: Optional[float] = Query(None, ge=0, le=1, description="最小空间一致性"),
    is_significant: Optional[bool] = Query(None, description="仅显示显著结果"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取空间-倾向性整合分析结果
    Get spatial-tendency integration analysis results

    This endpoint combines spatial clustering with character tendency analysis,
    showing how character usage patterns correlate with geographic clusters.

    Args:
        run_id: 整合分析运行ID
        character: 字符过滤（可选）
        cluster_id: 聚类ID过滤（可选）
        min_cluster_size: 最小聚类大小（可选）
        min_spatial_coherence: 最小空间一致性（可选，0-1）
        is_significant: 仅显示统计显著结果（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 整合分析结果列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_integration")

    query = """
        SELECT
            id,
            run_id,
            character,
            cluster_id,
            cluster_tendency_mean,
            cluster_tendency_std,
            cluster_size,
            n_villages_with_char,
            centroid_lon,
            centroid_lat,
            avg_distance_km,
            spatial_coherence,
            dominant_city,
            dominant_county,
            is_significant,
            avg_p_value
        FROM spatial_tendency_integration
        WHERE run_id = ?
    """
    params = [run_id]

    # 现场过滤：字符
    if character is not None:
        query += " AND character = ?"
        params.append(character)

    # 现场过滤：聚类ID
    if cluster_id is not None:
        query += " AND cluster_id = ?"
        params.append(cluster_id)

    # 现场过滤：最小聚类大小
    if min_cluster_size is not None:
        query += " AND cluster_size >= ?"
        params.append(min_cluster_size)

    # 现场过滤：最小空间一致性
    if min_spatial_coherence is not None:
        query += " AND spatial_coherence >= ?"
        params.append(min_spatial_coherence)

    # 现场过滤：显著性
    if is_significant is not None:
        query += " AND is_significant = ?"
        params.append(1 if is_significant else 0)

    query += " ORDER BY cluster_size DESC, spatial_coherence DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No integration results found for run_id: {run_id}"
        )

    return results


@router.get("/integration/by-character/{character}")
def get_integration_by_character(
    character: str,
    run_id: Optional[str] = Query(None, description="整合分析运行ID（留空使用活跃版本）"),
    min_spatial_coherence: Optional[float] = Query(None, ge=0, le=1, description="最小空间一致性"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取特定字符的空间-倾向性整合结果
    Get spatial-tendency integration results for a specific character

    Args:
        character: 目标字符
        run_id: 整合分析运行ID
        min_spatial_coherence: 最小空间一致性（可选）

    Returns:
        List[dict]: 该字符在各聚类中的表现
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_integration")

    query = """
        SELECT
            cluster_id,
            cluster_tendency_mean,
            cluster_tendency_std,
            cluster_size,
            n_villages_with_char,
            centroid_lon,
            centroid_lat,
            avg_distance_km,
            spatial_coherence,
            dominant_city,
            dominant_county,
            is_significant,
            avg_p_value
        FROM spatial_tendency_integration
        WHERE run_id = ? AND character = ?
    """
    params = [run_id, character]

    if min_spatial_coherence is not None:
        query += " AND spatial_coherence >= ?"
        params.append(min_spatial_coherence)

    query += " ORDER BY cluster_tendency_mean DESC"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No integration results found for character: {character}"
        )

    return {
        "character": character,
        "run_id": run_id,
        "total_clusters": len(results),
        "clusters": results
    }


@router.get("/integration/by-cluster/{cluster_id}")
def get_integration_by_cluster(
    cluster_id: int,
    run_id: Optional[str] = Query(None, description="整合分析运行ID（留空使用活跃版本）"),
    min_tendency: Optional[float] = Query(None, description="最小倾向值"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取特定聚类的空间-倾向性整合结果
    Get spatial-tendency integration results for a specific cluster

    Args:
        cluster_id: 聚类ID
        run_id: 整合分析运行ID
        min_tendency: 最小倾向值（可选）

    Returns:
        dict: 该聚类中各字符的表现
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_integration")

    query = """
        SELECT
            character,
            cluster_tendency_mean,
            cluster_tendency_std,
            cluster_size,
            n_villages_with_char,
            centroid_lon,
            centroid_lat,
            avg_distance_km,
            spatial_coherence,
            dominant_city,
            dominant_county,
            is_significant,
            avg_p_value
        FROM spatial_tendency_integration
        WHERE run_id = ? AND cluster_id = ?
    """
    params = [run_id, cluster_id]

    if min_tendency is not None:
        query += " AND cluster_tendency_mean >= ?"
        params.append(min_tendency)

    query += " ORDER BY cluster_tendency_mean DESC"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No integration results found for cluster_id: {cluster_id}"
        )

    return {
        "cluster_id": cluster_id,
        "run_id": run_id,
        "total_characters": len(results),
        "characters": results
    }


@router.get("/integration/summary")
def get_integration_summary(
    run_id: Optional[str] = Query(None, description="整合分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取空间-倾向性整合分析汇总统计
    Get spatial-tendency integration summary statistics

    Args:
        run_id: 整合分析运行ID

    Returns:
        dict: 汇总统计信息
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_integration")

    # 总体统计
    overall_query = """
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT character) as unique_characters,
            COUNT(DISTINCT cluster_id) as unique_clusters,
            AVG(cluster_tendency_mean) as avg_tendency,
            AVG(spatial_coherence) as avg_coherence,
            SUM(CASE WHEN is_significant = 1 THEN 1 ELSE 0 END) as significant_count
        FROM spatial_tendency_integration
        WHERE run_id = ?
    """
    overall = execute_single(db, overall_query, (run_id,))

    if not overall:
        raise HTTPException(
            status_code=404,
            detail=f"No integration summary found for run_id: {run_id}"
        )

    # 按字符统计
    char_query = """
        SELECT
            character,
            COUNT(*) as cluster_count,
            AVG(cluster_tendency_mean) as avg_tendency,
            AVG(spatial_coherence) as avg_coherence,
            SUM(n_villages_with_char) as total_villages
        FROM spatial_tendency_integration
        WHERE run_id = ?
        GROUP BY character
        ORDER BY avg_tendency DESC
    """
    top_characters = execute_query(db, char_query, (run_id,))

    # 按聚类统计
    cluster_query = """
        SELECT
            cluster_id,
            COUNT(*) as character_count,
            AVG(cluster_tendency_mean) as avg_tendency,
            AVG(spatial_coherence) as avg_coherence,
            MAX(cluster_size) as cluster_size,
            MAX(dominant_city) as dominant_city,
            MAX(dominant_county) as dominant_county
        FROM spatial_tendency_integration
        WHERE run_id = ?
        GROUP BY cluster_id
        ORDER BY cluster_size DESC
        LIMIT 10
    """
    top_clusters = execute_query(db, cluster_query, (run_id,))

    return {
        "run_id": run_id,
        "overall": overall,
        "top_characters": top_characters[:10],
        "top_clusters": top_clusters
    }
