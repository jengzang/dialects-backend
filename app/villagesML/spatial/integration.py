"""
空间-倾向性整合分析API
Spatial-Tendency Integration API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query, execute_single
from ..run_id_manager import get_run_id_manager
from ..schema_runtime import qcolumn, qtable, run_id_analysis_type

router = APIRouter(prefix="/spatial", tags=["spatial-integration"])


def _integration_schema(dbpath: str):
    table = qtable(dbpath, "spatial_tendency_integration")
    col = lambda name: qcolumn(dbpath, "spatial_tendency_integration", name)
    analysis_type = run_id_analysis_type(dbpath, "spatial_tendency_integration")
    return table, col, analysis_type


@router.get("/integration")
def get_spatial_tendency_integration(
    run_id: Optional[str] = Query(None, description="整合分析运行ID（留空使用活跃版本）"),
    character: Optional[str] = Query(None, description="字符过滤"),
    cluster_id: Optional[int] = Query(None, description="聚类ID过滤"),
    min_cluster_size: Optional[int] = Query(None, ge=1, description="最小聚类大小"),
    min_spatial_coherence: Optional[float] = Query(None, ge=0, le=1, description="最小空间一致性"),
    is_significant: Optional[bool] = Query(None, description="仅显示显著结果"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
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
    table, col, analysis_type = _integration_schema(dbpath)
    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(analysis_type)

    query = f"""
        SELECT
            {col("id")} as id,
            {col("run_id")} as run_id,
            {col("tendency_run_id")} as tendency_run_id,
            {col("spatial_run_id")} as spatial_run_id,
            {col("character")} as character,
            {col("character_category")} as character_category,
            {col("cluster_id")} as cluster_id,
            {col("cluster_tendency_mean")} as cluster_tendency_mean,
            {col("cluster_tendency_std")} as cluster_tendency_std,
            {col("global_tendency_mean")} as global_tendency_mean,
            {col("tendency_deviation")} as tendency_deviation,
            {col("cluster_size")} as cluster_size,
            {col("n_villages_with_char")} as n_villages_with_char,
            {col("centroid_lon")} as centroid_lon,
            {col("centroid_lat")} as centroid_lat,
            {col("avg_distance_km")} as avg_distance_km,
            {col("spatial_coherence")} as spatial_coherence,
            {col("spatial_specificity")} as spatial_specificity,
            {col("dominant_city")} as dominant_city,
            {col("dominant_county")} as dominant_county,
            {col("is_significant")} as is_significant,
            {col("p_value")} as p_value,
            {col("u_statistic")} as u_statistic
        FROM {table}
        WHERE {col("run_id")} = ?
    """
    params = [run_id]

    # 现场过滤：字符
    if character is not None:
        query += f" AND {col('character')} = ?"
        params.append(character)

    # 现场过滤：聚类ID
    if cluster_id is not None:
        query += f" AND {col('cluster_id')} = ?"
        params.append(cluster_id)

    # 现场过滤：最小聚类大小
    if min_cluster_size is not None:
        query += f" AND {col('cluster_size')} >= ?"
        params.append(min_cluster_size)

    # 现场过滤：最小空间一致性
    if min_spatial_coherence is not None:
        query += f" AND {col('spatial_coherence')} >= ?"
        params.append(min_spatial_coherence)

    # 现场过滤：显著性
    if is_significant is not None:
        query += f" AND {col('is_significant')} = ?"
        params.append(1 if is_significant else 0)

    query += f" ORDER BY {col('cluster_size')} DESC, {col('spatial_coherence')} DESC LIMIT ?"
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
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
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
    table, col, analysis_type = _integration_schema(dbpath)
    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(analysis_type)

    query = f"""
        SELECT
            {col("cluster_id")} as cluster_id,
            {col("cluster_tendency_mean")} as cluster_tendency_mean,
            {col("cluster_tendency_std")} as cluster_tendency_std,
            {col("global_tendency_mean")} as global_tendency_mean,
            {col("tendency_deviation")} as tendency_deviation,
            {col("cluster_size")} as cluster_size,
            {col("n_villages_with_char")} as n_villages_with_char,
            {col("centroid_lon")} as centroid_lon,
            {col("centroid_lat")} as centroid_lat,
            {col("avg_distance_km")} as avg_distance_km,
            {col("spatial_coherence")} as spatial_coherence,
            {col("spatial_specificity")} as spatial_specificity,
            {col("dominant_city")} as dominant_city,
            {col("dominant_county")} as dominant_county,
            {col("is_significant")} as is_significant,
            {col("p_value")} as p_value,
            {col("u_statistic")} as u_statistic
        FROM {table}
        WHERE {col("run_id")} = ? AND {col("character")} = ?
    """
    params = [run_id, character]

    if min_spatial_coherence is not None:
        query += f" AND {col('spatial_coherence')} >= ?"
        params.append(min_spatial_coherence)

    query += f" ORDER BY {col('cluster_tendency_mean')} DESC"

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
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
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
    table, col, analysis_type = _integration_schema(dbpath)
    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(analysis_type)

    query = f"""
        SELECT
            {col("character")} as character,
            {col("character_category")} as character_category,
            {col("cluster_tendency_mean")} as cluster_tendency_mean,
            {col("cluster_tendency_std")} as cluster_tendency_std,
            {col("global_tendency_mean")} as global_tendency_mean,
            {col("tendency_deviation")} as tendency_deviation,
            {col("cluster_size")} as cluster_size,
            {col("n_villages_with_char")} as n_villages_with_char,
            {col("centroid_lon")} as centroid_lon,
            {col("centroid_lat")} as centroid_lat,
            {col("avg_distance_km")} as avg_distance_km,
            {col("spatial_coherence")} as spatial_coherence,
            {col("spatial_specificity")} as spatial_specificity,
            {col("dominant_city")} as dominant_city,
            {col("dominant_county")} as dominant_county,
            {col("is_significant")} as is_significant,
            {col("p_value")} as p_value,
            {col("u_statistic")} as u_statistic
        FROM {table}
        WHERE {col("run_id")} = ? AND {col("cluster_id")} = ?
    """
    params = [run_id, cluster_id]

    if min_tendency is not None:
        query += f" AND {col('cluster_tendency_mean')} >= ?"
        params.append(min_tendency)

    query += f" ORDER BY {col('cluster_tendency_mean')} DESC"

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
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
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
    table, col, analysis_type = _integration_schema(dbpath)
    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(analysis_type)

    # 总体统计
    overall_query = f"""
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT {col("character")}) as unique_characters,
            COUNT(DISTINCT {col("cluster_id")}) as unique_clusters,
            AVG({col("cluster_tendency_mean")}) as avg_tendency,
            AVG({col("spatial_coherence")}) as avg_coherence,
            SUM(CASE WHEN {col("is_significant")} = 1 THEN 1 ELSE 0 END) as significant_count
        FROM {table}
        WHERE {col("run_id")} = ?
    """
    overall = execute_single(db, overall_query, (run_id,))

    if not overall:
        raise HTTPException(
            status_code=404,
            detail=f"No integration summary found for run_id: {run_id}"
        )

    # 按字符统计
    char_query = f"""
        SELECT
            {col("character")} as character,
            COUNT(*) as cluster_count,
            AVG({col("cluster_tendency_mean")}) as avg_tendency,
            AVG({col("spatial_coherence")}) as avg_coherence,
            SUM({col("n_villages_with_char")}) as total_villages
        FROM {table}
        WHERE {col("run_id")} = ?
        GROUP BY {col("character")}
        ORDER BY avg_tendency DESC
    """
    top_characters = execute_query(db, char_query, (run_id,))

    # 按聚类统计
    cluster_query = f"""
        SELECT
            {col("cluster_id")} as cluster_id,
            COUNT(*) as character_count,
            AVG({col("cluster_tendency_mean")}) as avg_tendency,
            AVG({col("spatial_coherence")}) as avg_coherence,
            MAX({col("cluster_size")}) as cluster_size,
            MAX({col("dominant_city")}) as dominant_city,
            MAX({col("dominant_county")}) as dominant_county
        FROM {table}
        WHERE {col("run_id")} = ?
        GROUP BY {col("cluster_id")}
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


@router.get("/integration/available-characters")
def get_available_characters(
    run_id: Optional[str] = Query(None, description="整合分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取可用字符列表
    Get list of available characters for spatial-tendency integration

    Returns all characters that have spatial-tendency integration data,
    along with their statistics to help frontend avoid querying non-existent characters.

    Args:
        run_id: 整合分析运行ID（留空使用活跃版本）

    Returns:
        dict: 包含可用字符列表及其统计信息
    """
    # 如果未指定run_id，使用活跃版本
    table, col, analysis_type = _integration_schema(dbpath)
    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(analysis_type)

    query = f"""
        SELECT
            {col("character")} as character,
            {col("character_category")} as category,
            COUNT(DISTINCT {col("cluster_id")}) as total_clusters,
            SUM({col("n_villages_with_char")}) as total_villages,
            AVG({col("cluster_tendency_mean")}) as avg_tendency,
            AVG({col("spatial_coherence")}) as avg_spatial_coherence,
            SUM(CASE WHEN {col("is_significant")} = 1 THEN 1 ELSE 0 END) as significant_clusters
        FROM {table}
        WHERE {col("run_id")} = ?
        GROUP BY {col("character")}, {col("character_category")}
        ORDER BY {col("character")}
    """

    results = execute_query(db, query, (run_id,))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No characters found for run_id: {run_id}"
        )

    return {
        "run_id": run_id,
        "total_characters": len(results),
        "characters": results
    }


@router.get("/integration/clusterlist")
def get_cluster_list(
    run_id: Optional[str] = Query(None, description="整合分析运行ID（留空使用活跃版本）"),
    min_cluster_size: Optional[int] = Query(None, ge=1, description="最小聚类大小"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取聚类列表（含地区信息）
    Get cluster list with geographic information

    Returns a list of all clusters with their basic information including
    dominant city/county, size, location, and character count.

    Args:
        run_id: 整合分析运行ID（留空使用活跃版本）
        min_cluster_size: 最小聚类大小（可选）

    Returns:
        dict: 包含聚类列表
    """
    # 如果未指定run_id，使用活跃版本
    table, col, analysis_type = _integration_schema(dbpath)
    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(analysis_type)

    query = f"""
        SELECT
            {col("cluster_id")} as cluster_id,
            MAX({col("cluster_size")}) as cluster_size,
            MAX({col("dominant_city")}) as dominant_city,
            MAX({col("dominant_county")}) as dominant_county,
            MAX({col("centroid_lon")}) as centroid_lon,
            MAX({col("centroid_lat")}) as centroid_lat,
            COUNT(DISTINCT {col("character")}) as total_characters,
            AVG({col("cluster_tendency_mean")}) as avg_tendency,
            AVG({col("spatial_coherence")}) as avg_spatial_coherence,
            SUM(CASE WHEN {col("is_significant")} = 1 THEN 1 ELSE 0 END) as significant_characters
        FROM {table}
        WHERE {col("run_id")} = ?
        GROUP BY {col("cluster_id")}
    """
    params = [run_id]

    # 添加聚类大小过滤
    if min_cluster_size is not None:
        query = f"""
        SELECT * FROM (
            {query}
        ) WHERE cluster_size >= ?
        """
        params.append(min_cluster_size)

    query += " ORDER BY cluster_size DESC"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No clusters found for run_id: {run_id}"
        )

    return {
        "run_id": run_id,
        "total_clusters": len(results),
        "clusters": results
    }
