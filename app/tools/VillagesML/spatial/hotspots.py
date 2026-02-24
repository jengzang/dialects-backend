"""
空间热点API
Spatial Hotspots API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single
from ..config import DEFAULT_RUN_ID
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/spatial")


@router.get("/hotspots")
def get_spatial_hotspots(
    run_id: Optional[str] = Query(None, description="空间分析运行ID（留空使用活跃版本）"),
    min_density: Optional[float] = Query(None, description="最小密度阈值"),
    min_village_count: Optional[int] = Query(None, ge=1, description="最小村庄数量"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取空间密度热点
    Get spatial density hotspots (KDE analysis results)

    Args:
        run_id: 空间分析运行ID（留空使用活跃版本）
        min_density: 最小密度阈值（可选）
        min_village_count: 最小村庄数量（可选）

    Returns:
        List[dict]: 热点列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_hotspots")

    query = """
        SELECT
            hotspot_id,
            center_lon,
            center_lat,
            density_score,
            village_count,
            radius_km
        FROM spatial_hotspots
        WHERE run_id = ?
    """
    params = [run_id]

    # 现场过滤：最小密度
    if min_density is not None:
        query += " AND density_score >= ?"
        params.append(min_density)

    # 现场过滤：最小村庄数
    if min_village_count is not None:
        query += " AND village_count >= ?"
        params.append(min_village_count)

    query += " ORDER BY density_score DESC"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No spatial hotspots found for run_id: {run_id}"
        )

    return results


@router.get("/hotspots/{hotspot_id}")
def get_hotspot_detail(
    hotspot_id: int,
    run_id: Optional[str] = Query(None, description="空间分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取单个热点详情
    Get details for a specific hotspot

    Args:
        hotspot_id: 热点ID
        run_id: 空间分析运行ID（留空使用活跃版本）

    Returns:
        dict: 热点详情
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_hotspots")

    query = """
        SELECT
            hotspot_id,
            center_lon,
            center_lat,
            density_score,
            village_count,
            radius_km
        FROM spatial_hotspots
        WHERE run_id = ? AND hotspot_id = ?
    """

    result = execute_single(db, query, (run_id, hotspot_id))

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Hotspot {hotspot_id} not found"
        )

    return result


@router.get("/clusters")
def get_spatial_clusters(
    run_id: Optional[str] = Query(None, description="空间分析运行ID（留空使用活跃版本）"),
    cluster_id: Optional[int] = Query(None, description="聚类ID过滤"),
    min_size: Optional[int] = Query(None, ge=1, description="最小聚类大小"),
    limit: int = Query(100, ge=0, description="返回记录数（0表示返回所有）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取DBSCAN空间聚类结果
    Get DBSCAN spatial clustering results

    Args:
        run_id: 空间分析运行ID（留空使用活跃版本）
        cluster_id: 聚类ID（可选，-1表示噪声点）
        min_size: 最小聚类大小（可选）
        limit: 返回记录数（0表示返回所有，默认100）

    Returns:
        List[dict]: 聚类结果列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_hotspots")

    query = """
        SELECT
            cluster_id,
            cluster_size,
            centroid_lon,
            centroid_lat,
            avg_distance_km
        FROM spatial_clusters
        WHERE run_id = ?
    """
    params = [run_id]

    # 现场过滤：聚类ID
    if cluster_id is not None:
        query += " AND cluster_id = ?"
        params.append(cluster_id)

    # 现场过滤：最小聚类大小（需要子查询）
    if min_size is not None:
        query = f"""
        SELECT * FROM (
            {query}
        ) WHERE cluster_id IN (
            SELECT cluster_id
            FROM spatial_clusters
            WHERE run_id = ?
            GROUP BY cluster_id
            HAVING COUNT(*) >= ?
        )
        """
        params.extend([run_id, min_size])

    query += " ORDER BY cluster_id"

    # 只有当 limit > 0 时才添加 LIMIT 子句
    if limit > 0:
        query += " LIMIT ?"
        params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No spatial clusters found for run_id: {run_id}"
        )

    return results


@router.get("/clusters/summary")
def get_cluster_summary(
    run_id: Optional[str] = Query(None, description="空间分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取聚类汇总统计（仅统计信息，不返回具体数据）
    Get clustering summary statistics (statistics only, no detailed data)

    Args:
        run_id: 空间分析运行ID（留空使用活跃版本）

    Returns:
        dict: 聚类汇总统计信息
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("spatial_hotspots")

    query = """
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT cluster_id) as unique_clusters,
            AVG(cluster_size) as avg_cluster_size,
            MIN(cluster_size) as min_cluster_size,
            MAX(cluster_size) as max_cluster_size,
            SUM(cluster_size) as total_villages,
            SUM(CASE WHEN cluster_id = -1 THEN 1 ELSE 0 END) as noise_count,
            AVG(avg_distance_km) as avg_distance,
            MIN(centroid_lon) as min_lon,
            MAX(centroid_lon) as max_lon,
            MIN(centroid_lat) as min_lat,
            MAX(centroid_lat) as max_lat
        FROM spatial_clusters
        WHERE run_id = ?
    """

    result = execute_single(db, query, (run_id,))

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No cluster summary found for run_id: {run_id}"
        )

    # 计算有效聚类数（排除噪声点）
    valid_clusters = result["unique_clusters"]
    if result["noise_count"] > 0:
        valid_clusters -= 1

    return {
        "run_id": run_id,
        "total_records": result["total_records"],
        "total_clusters": valid_clusters,
        "noise_points": result["noise_count"],
        "total_villages": result["total_villages"],
        "cluster_size": {
            "avg": result["avg_cluster_size"],
            "min": result["min_cluster_size"],
            "max": result["max_cluster_size"]
        },
        "spatial_extent": {
            "avg_distance_km": result["avg_distance"],
            "lon_range": [result["min_lon"], result["max_lon"]],
            "lat_range": [result["min_lat"], result["max_lat"]]
        }
    }



@router.get("/clusters/available-runs")
def get_available_cluster_runs(db: sqlite3.Connection = Depends(get_db)):
    """
    获取所有可用的聚类 run_id 及其统计信息
    Get all available clustering run_ids with statistics

    Returns:
        dict: 包含活跃 run_id 和所有可用 run_id 列表
    """
    query = """
        SELECT
            run_id,
            COUNT(*) as total_records,
            COUNT(DISTINCT cluster_id) as unique_clusters,
            MIN(cluster_id) as min_cluster_id,
            MAX(cluster_id) as max_cluster_id,
            AVG(cluster_size) as avg_cluster_size,
            MAX(cluster_size) as max_cluster_size,
            SUM(CASE WHEN cluster_id = -1 THEN 1 ELSE 0 END) as noise_count
        FROM spatial_clusters
        GROUP BY run_id
        ORDER BY run_id
    """

    results = execute_query(db, query, ())

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No clustering runs found"
        )

    # 获取当前活跃的 run_id
    active_run_id = run_id_manager.get_active_run_id("spatial_hotspots")

    # 添加 is_active 标记
    for result in results:
        result["is_active"] = (result["run_id"] == active_run_id)

    return {
        "active_run_id": active_run_id,
        "available_runs": results
    }
