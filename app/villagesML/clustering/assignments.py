"""
聚类分配API
Cluster Assignment API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query, execute_single
from ..models import ClusterAssignment, ClusterProfile, ClusteringMetrics
from ..run_id_manager import get_run_id_manager
from ..schema_runtime import qcolumn, qtable, run_id_analysis_type, normalize_region_level
from ..schema_keys import C, T

router = APIRouter(prefix="/clustering")


@router.get("/assignments", response_model=List[ClusterAssignment])
def get_cluster_assignments(
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    algorithm: str = Query("kmeans", description="聚类算法", pattern="^(kmeans|dbscan|gmm)$"),
    region_level: str = Query("county", description="区域级别", pattern="^(city|county|township)$"),
    cluster_id: Optional[int] = Query(None, description="聚类ID过滤"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
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
        run_id = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.CLUSTER_ASSIGNMENTS)
        )

    table = qtable(dbpath, T.CLUSTER_ASSIGNMENTS)
    run_id_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.RUN_ID)
    algorithm_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.ALGORITHM)
    region_level_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.REGION_LEVEL)
    region_name_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.REGION_NAME)
    cluster_id_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.CLUSTER_ID)
    distance_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.DISTANCE_TO_CENTROID)

    query = f"""
        SELECT
            {region_name_col} as region_name,
            {cluster_id_col} as cluster_id,
            {distance_col} as distance_to_centroid
        FROM {table}
        WHERE {run_id_col} = ? AND {algorithm_col} = ? AND {region_level_col} = ?
    """
    params = [run_id, algorithm, normalize_region_level(dbpath, T.CLUSTER_ASSIGNMENTS, region_level)]

    # 现场过滤：聚类ID
    if cluster_id is not None:
        query += f" AND {cluster_id_col} = ?"
        params.append(cluster_id)

    query += f" ORDER BY {cluster_id_col}, {region_name_col}"

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
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
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
        run_id = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.CLUSTER_ASSIGNMENTS)
        )

    table = qtable(dbpath, T.CLUSTER_ASSIGNMENTS)
    run_id_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.RUN_ID)
    algorithm_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.ALGORITHM)
    region_level_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.REGION_LEVEL)
    region_name_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.REGION_NAME)
    cluster_id_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.CLUSTER_ID)
    distance_col = qcolumn(dbpath, T.CLUSTER_ASSIGNMENTS, C.CLUSTER_ASSIGNMENTS.DISTANCE_TO_CENTROID)

    query = f"""
        SELECT
            {region_name_col} as region_name,
            {cluster_id_col} as cluster_id,
            {distance_col} as distance_to_centroid
        FROM {table}
        WHERE {run_id_col} = ? AND {region_name_col} = ? AND {algorithm_col} = ? AND {region_level_col} = ?
    """

    result = execute_single(db, query, (run_id, region_name, algorithm, normalize_region_level(dbpath, T.CLUSTER_ASSIGNMENTS, region_level)))

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
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
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
        run_id = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.CLUSTER_PROFILES)
        )

    table = qtable(dbpath, T.CLUSTER_PROFILES)
    run_id_col = qcolumn(dbpath, T.CLUSTER_PROFILES, C.CLUSTER_PROFILES.RUN_ID)
    algorithm_col = qcolumn(dbpath, T.CLUSTER_PROFILES, C.CLUSTER_PROFILES.ALGORITHM)
    cluster_id_col = qcolumn(dbpath, T.CLUSTER_PROFILES, C.CLUSTER_PROFILES.CLUSTER_ID)
    cluster_size_col = qcolumn(dbpath, T.CLUSTER_PROFILES, C.CLUSTER_PROFILES.CLUSTER_SIZE)
    top_features_col = qcolumn(dbpath, T.CLUSTER_PROFILES, C.CLUSTER_PROFILES.TOP_FEATURES_JSON)
    top_semantic_col = qcolumn(dbpath, T.CLUSTER_PROFILES, C.CLUSTER_PROFILES.TOP_SEMANTIC_CATEGORIES_JSON)
    top_suffixes_col = qcolumn(dbpath, T.CLUSTER_PROFILES, C.CLUSTER_PROFILES.TOP_SUFFIXES_JSON)

    query = f"""
        SELECT
            {cluster_id_col} as cluster_id,
            {cluster_size_col} as cluster_size,
            {top_features_col} as top_features_json,
            {top_semantic_col} as top_semantic_categories_json,
            {top_suffixes_col} as top_suffixes_json
        FROM {table}
        WHERE {run_id_col} = ? AND {algorithm_col} = ?
    """
    params = [run_id, algorithm]

    # 现场过滤：聚类ID
    if cluster_id is not None:
        query += f" AND {cluster_id_col} = ?"
        params.append(cluster_id)

    query += f" ORDER BY {cluster_id_col}"

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
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
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
        run_id = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.CLUSTERING_METRICS)
        )

    table = qtable(dbpath, T.CLUSTERING_METRICS)
    run_id_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.RUN_ID)
    algorithm_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.ALGORITHM)
    k_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.K)
    silhouette_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.SILHOUETTE_SCORE)
    davies_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.DAVIES_BOULDIN_INDEX)
    calinski_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.CALINSKI_HARABASZ_SCORE)

    query = f"""
        SELECT
            {algorithm_col} as algorithm,
            {k_col} as k,
            {silhouette_col} as silhouette_score,
            {davies_col} as davies_bouldin_index,
            {calinski_col} as calinski_harabasz_score
        FROM {table}
        WHERE {run_id_col} = ?
    """
    params = [run_id]

    # 现场过滤：算法
    if algorithm is not None:
        query += f" AND {algorithm_col} = ?"
        params.append(algorithm)

    query += f" ORDER BY {algorithm_col}, {k_col}"

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
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
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
        run_id = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.CLUSTERING_METRICS)
        )

    # 根据指标选择排序方向（silhouette和CH越大越好，DB越小越好）
    order = "DESC" if metric in ["silhouette_score", "calinski_harabasz_score"] else "ASC"
    metric_column_map = {
        "silhouette_score": qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.SILHOUETTE_SCORE),
        "davies_bouldin_index": qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.DAVIES_BOULDIN_INDEX),
        "calinski_harabasz_score": qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.CALINSKI_HARABASZ_SCORE),
    }
    metric_col = metric_column_map.get(metric, qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.SILHOUETTE_SCORE))
    table = qtable(dbpath, T.CLUSTERING_METRICS)
    run_id_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.RUN_ID)
    algorithm_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.ALGORITHM)
    k_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.K)
    silhouette_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.SILHOUETTE_SCORE)
    davies_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.DAVIES_BOULDIN_INDEX)
    calinski_col = qcolumn(dbpath, T.CLUSTERING_METRICS, C.CLUSTERING_METRICS.CALINSKI_HARABASZ_SCORE)

    query = f"""
        SELECT
            {algorithm_col} as algorithm,
            {k_col} as k,
            {silhouette_col} as silhouette_score,
            {davies_col} as davies_bouldin_index,
            {calinski_col} as calinski_harabasz_score
        FROM {table}
        WHERE {run_id_col} = ? AND {algorithm_col} = ?
        ORDER BY {metric_col} {order}
        LIMIT 1
    """

    result = execute_single(db, query, (run_id, algorithm))

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No clustering metrics found for algorithm: {algorithm}"
        )

    return result
