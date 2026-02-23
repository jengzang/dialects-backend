"""
聚类分配API
Cluster Assignment API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single
from ..config import DEFAULT_RUN_ID, DEFAULT_CLUSTERING_RUN_ID
from ..models import ClusterAssignment, ClusterProfile, ClusteringMetrics
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/clustering", tags=["clustering"])


@router.get("/assignments", response_model=List[ClusterAssignment])
def get_cluster_assignments(
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    algorithm: str = Query("kmeans", description="聚类算法", pattern="^(kmeans|dbscan|gmm)$"),
    region_level: str = Query("county", description="区域级别", pattern="^(city|county|township)$"),
    cluster_id: Optional[int] = Query(None, description="聚类ID过滤"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取聚类分配结果
    Get cluster assignments

    Args:
        run_id: 分析运行ID
        algorithm: 聚类算法 (kmeans/dbscan/gmm)
        region_level: 区域级别
        cluster_id: 聚类ID（可选）

    Returns:
        List[ClusterAssignment]: 聚类分配列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("clustering_county")

    query = """
        SELECT
            region_name,
            cluster_id,
            distance_to_centroid
        FROM cluster_assignments
        WHERE run_id = ? AND algorithm = ? AND region_level = ?
    """
    params = [run_id, algorithm, region_level]

    # 现场过滤：聚类ID
    if cluster_id is not None:
        query += " AND cluster_id = ?"
        params.append(cluster_id)

    query += " ORDER BY cluster_id, region_name"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No cluster assignments found for algorithm: {algorithm}"
        )

    return results


@router.get("/assignments/by-region", response_model=ClusterAssignment)
def get_cluster_assignment_by_region(
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    region_name: str = Query(..., description="区域名称"),
    algorithm: str = Query("kmeans", description="聚类算法", pattern="^(kmeans|dbscan|gmm)$"),
    region_level: str = Query("county", description="区域级别"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取指定区域的聚类分配
    Get cluster assignment for a specific region

    Args:
        run_id: 分析运行ID
        region_name: 区域名称
        algorithm: 聚类算法
        region_level: 区域级别

    Returns:
        ClusterAssignment: 聚类分配
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("clustering_county")

    query = """
        SELECT
            region_name,
            cluster_id,
            distance_to_centroid
        FROM cluster_assignments
        WHERE run_id = ? AND region_name = ? AND algorithm = ? AND region_level = ?
    """

    result = execute_single(db, query, (run_id, region_name, algorithm, region_level))

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No cluster assignment found for region: {region_name}"
        )

    return result


@router.get("/profiles")
def get_cluster_profiles(
    run_id: Optional[str] = Query(None, description="聚类运行ID（留空使用活跃版本）"),
    algorithm: str = Query("kmeans", description="聚类算法", pattern="^(kmeans|dbscan|gmm)$"),
    cluster_id: Optional[int] = Query(None, description="聚类ID"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取聚类画像
    Get cluster profiles

    Args:
        run_id: 分析运行ID
        algorithm: 聚类算法
        cluster_id: 聚类ID（可选）

    Returns:
        List[ClusterProfile]: 聚类画像列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("clustering_county")

    query = """
        SELECT
            cluster_id,
            cluster_size,
            top_features_json,
            top_semantic_categories_json,
            top_suffixes_json
        FROM cluster_profiles
        WHERE run_id = ? AND algorithm = ?
    """
    params = [run_id, algorithm]

    # 现场过滤：聚类ID
    if cluster_id is not None:
        query += " AND cluster_id = ?"
        params.append(cluster_id)

    query += " ORDER BY cluster_id"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No cluster profiles found for algorithm: {algorithm}"
        )

    # 解析JSON字段（如果存储为JSON字符串）
    import json
    for result in results:
        if isinstance(result.get("top_features_json"), str):
            result["top_features_json"] = json.loads(result["top_features_json"])
        if isinstance(result.get("top_semantic_categories_json"), str):
            result["top_semantic_categories_json"] = json.loads(result["top_semantic_categories_json"])
        if isinstance(result.get("top_suffixes_json"), str):
            result["top_suffixes_json"] = json.loads(result["top_suffixes_json"])

    return results


@router.get("/metrics", response_model=List[ClusteringMetrics])
def get_clustering_metrics(
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    algorithm: Optional[str] = Query(None, description="聚类算法", pattern="^(kmeans|dbscan|gmm)$"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取聚类质量指标
    Get clustering quality metrics

    Args:
        run_id: 分析运行ID
        algorithm: 聚类算法（可选）

    Returns:
        List[ClusteringMetrics]: 聚类指标列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("clustering_county")

    query = """
        SELECT
            algorithm,
            k,
            silhouette_score,
            davies_bouldin_index,
            calinski_harabasz_score
        FROM clustering_metrics
        WHERE run_id = ?
    """
    params = [run_id]

    # 现场过滤：算法
    if algorithm is not None:
        query += " AND algorithm = ?"
        params.append(algorithm)

    query += " ORDER BY algorithm, k"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No clustering metrics found for run_id: {run_id}"
        )

    return results


@router.get("/metrics/best", response_model=ClusteringMetrics)
def get_best_clustering(
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    algorithm: str = Query("kmeans", description="聚类算法", pattern="^(kmeans|dbscan|gmm)$"),
    metric: str = Query("silhouette_score", description="优化指标"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取最优聚类配置
    Get best clustering configuration

    Args:
        run_id: 分析运行ID
        algorithm: 聚类算法
        metric: 优化指标

    Returns:
        ClusteringMetrics: 最优聚类指标
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("clustering_county")

    # 根据指标选择排序方向（silhouette和CH越大越好，DB越小越好）
    order = "DESC" if metric in ["silhouette_score", "calinski_harabasz_score"] else "ASC"

    query = f"""
        SELECT
            algorithm,
            k,
            silhouette_score,
            davies_bouldin_index,
            calinski_harabasz_score
        FROM clustering_metrics
        WHERE run_id = ? AND algorithm = ?
        ORDER BY {metric} {order}
        LIMIT 1
    """

    result = execute_single(db, query, (run_id, algorithm))

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No clustering metrics found for algorithm: {algorithm}"
        )

    return result
