"""
区域聚合数据API
Regional Aggregates API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single

router = APIRouter(prefix="/regional", tags=["regional-aggregates"])


@router.get("/aggregates/city")
def get_city_aggregates(
    city_name: Optional[str] = Query(None, description="城市名称"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取城市级别聚合数据
    Get city-level aggregate statistics

    Args:
        city_name: 城市名称（可选）

    Returns:
        List[dict]: 城市聚合数据
    """
    query = """
        SELECT *
        FROM city_aggregates
    """
    params = []

    if city_name is not None:
        query += " WHERE city = ?"
        params.append(city_name)

    query += " ORDER BY total_villages DESC"

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
    db: sqlite3.Connection = Depends(get_db)
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
    query = """
        SELECT *
        FROM county_aggregates
        WHERE 1=1
    """
    params = []

    if county_name is not None:
        query += " AND county = ?"
        params.append(county_name)

    if city_name is not None:
        query += " AND city = ?"
        params.append(city_name)

    query += " ORDER BY total_villages DESC"

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
    db: sqlite3.Connection = Depends(get_db)
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
    query = """
        SELECT *
        FROM town_aggregates
        WHERE 1=1
    """
    params = []

    if town_name is not None:
        query += " AND town = ?"
        params.append(town_name)

    if county_name is not None:
        query += " AND county = ?"
        params.append(county_name)

    query += " ORDER BY total_villages DESC LIMIT ?"
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
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
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
    query = """
        SELECT
            region_level,
            region_name,
            total_villages as village_count,
            avg_local_density as avg_density,
            avg_nn_distance,
            avg_isolation_score,
            spatial_dispersion
        FROM region_spatial_aggregates
        WHERE region_level = ?
    """
    params = [region_level]

    if region_name is not None:
        query += " AND region_name = ?"
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
    db: sqlite3.Connection = Depends(get_db)
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
    query = """
        SELECT
            region_id,
            region_name,
            region_level,
            N_villages,
            created_at
        FROM region_vectors
        WHERE 1=1
    """
    params = []

    if region_name is not None:
        query += " AND region_name = ?"
        params.append(region_name)

    query += " ORDER BY region_name LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No region vectors found"
        )

    return results
