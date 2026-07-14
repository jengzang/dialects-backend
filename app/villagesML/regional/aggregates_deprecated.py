"""
区域聚合数据API
Regional Aggregates API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query, execute_single
from ..schema_runtime import normalize_region_level, qcolumn, qtable

router = APIRouter(prefix="/regional")


@router.get("/aggregates/city")
def get_city_aggregates(
    city_name: Optional[str] = Query(None, description="城市名称"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取城市级别聚合数据
    Get city-level aggregate statistics

    Args:
        city_name: 城市名称（可选）

    Returns:
        List[dict]: 城市聚合数据
    """
    table = qtable(dbpath, "city_aggregates")
    city_col = qcolumn(dbpath, "city_aggregates", "city")
    total_villages_col = qcolumn(dbpath, "city_aggregates", "total_villages")

    query = f"""
        SELECT *
        FROM {table}
    """
    params = []

    if city_name is not None:
        query += f" WHERE {city_col} = ?"
        params.append(city_name)

    query += f" ORDER BY {total_villages_col} DESC"

    results = execute_query(db, query, tuple(params)) if params else execute_query(db, query, ())

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No city aggregates found"
        )

    return results


@router.get("/aggregates/county")
def get_county_aggregates(
    county_name: Optional[str] = Query(None, description="县区名称"),
    city_name: Optional[str] = Query(None, description="所属城市"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取县区级别聚合数据
    Get county-level aggregate statistics

    Args:
        county_name: 县区名称（可选）
        city_name: 所属城市（可选）

    Returns:
        List[dict]: 县区聚合数据
    """
    table = qtable(dbpath, "county_aggregates")
    city_col = qcolumn(dbpath, "county_aggregates", "city")
    county_col = qcolumn(dbpath, "county_aggregates", "county")
    total_villages_col = qcolumn(dbpath, "county_aggregates", "total_villages")

    query = f"""
        SELECT *
        FROM {table}
        WHERE 1=1
    """
    params = []

    if county_name is not None:
        query += f" AND {county_col} = ?"
        params.append(county_name)

    if city_name is not None:
        query += f" AND {city_col} = ?"
        params.append(city_name)

    query += f" ORDER BY {total_villages_col} DESC"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No county aggregates found"
        )

    return results


@router.get("/aggregates/town")
def get_town_aggregates(
    town_name: Optional[str] = Query(None, description="乡镇名称"),
    county_name: Optional[str] = Query(None, description="所属县区"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取乡镇级别聚合数据
    Get town-level aggregate statistics

    Args:
        town_name: 乡镇名称（可选）
        county_name: 所属县区（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 乡镇聚合数据
    """
    table = qtable(dbpath, "town_aggregates")
    county_col = qcolumn(dbpath, "town_aggregates", "county")
    town_col = qcolumn(dbpath, "town_aggregates", "town")
    total_villages_col = qcolumn(dbpath, "town_aggregates", "total_villages")

    query = f"""
        SELECT *
        FROM {table}
        WHERE 1=1
    """
    params = []

    if town_name is not None:
        query += f" AND {town_col} = ?"
        params.append(town_name)

    if county_name is not None:
        query += f" AND {county_col} = ?"
        params.append(county_name)

    query += f" ORDER BY {total_villages_col} DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No town aggregates found"
        )

    return results


@router.get("/spatial-aggregates")
def get_region_spatial_aggregates(
    region_level: str = Query(..., description="区域级别"),
    region_name: Optional[str] = Query(None, description="区域名称"),
    limit: int = Query(10000, ge=1, le=10000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取区域空间聚合数据
    Get regional spatial aggregate statistics

    Args:
        region_level: 区域级别（city/county/town）
        region_name: 区域名称（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 区域空间聚合数据
    """
    table = qtable(dbpath, "region_spatial_aggregates")
    region_level_col = qcolumn(dbpath, "region_spatial_aggregates", "region_level")
    region_name_col = qcolumn(dbpath, "region_spatial_aggregates", "region_name")
    total_villages_col = qcolumn(dbpath, "region_spatial_aggregates", "total_villages")
    avg_local_density_col = qcolumn(dbpath, "region_spatial_aggregates", "avg_local_density")
    avg_nn_distance_col = qcolumn(dbpath, "region_spatial_aggregates", "avg_nn_distance")
    avg_isolation_score_col = qcolumn(dbpath, "region_spatial_aggregates", "avg_isolation_score")
    spatial_dispersion_col = qcolumn(dbpath, "region_spatial_aggregates", "spatial_dispersion")

    query = f"""
        SELECT
            {region_level_col} as region_level,
            {region_name_col} as region_name,
            {total_villages_col} as village_count,
            {avg_local_density_col} as avg_density,
            {avg_nn_distance_col} as avg_nn_distance,
            {avg_isolation_score_col} as avg_isolation_score,
            {spatial_dispersion_col} as spatial_dispersion
        FROM {table}
        WHERE {region_level_col} = ?
    """
    params = [normalize_region_level(dbpath, "region_spatial_aggregates", region_level)]

    if region_name is not None:
        query += f" AND {region_name_col} = ?"
        params.append(region_name)

    query += " ORDER BY village_count DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No spatial aggregates found for region_level: {region_level}"
        )

    return results


@router.get("/vectors")
def get_region_vectors(
    region_name: Optional[str] = Query(None, description="区域名称"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取区域特征向量
    Get regional feature vectors

    Args:
        region_name: 区域名称（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 区域特征向量（不包含向量数据，仅元数据）
    """
    table = qtable(dbpath, "region_vectors")
    region_id_col = qcolumn(dbpath, "region_vectors", "region_id")
    region_name_col = qcolumn(dbpath, "region_vectors", "region_name")
    region_level_col = qcolumn(dbpath, "region_vectors", "region_level")
    n_villages_col = qcolumn(dbpath, "region_vectors", "N_villages")
    created_at_col = qcolumn(dbpath, "region_vectors", "created_at")

    query = f"""
        SELECT
            {region_id_col} as region_id,
            {region_name_col} as region_name,
            {region_level_col} as region_level,
            {n_villages_col} as N_villages,
            {created_at_col} as created_at
        FROM {table}
        WHERE 1=1
    """
    params = []

    if region_name is not None:
        query += f" AND {region_name_col} = ?"
        params.append(region_name)

    query += f" ORDER BY {region_name_col} LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No region vectors found"
        )

    return results
