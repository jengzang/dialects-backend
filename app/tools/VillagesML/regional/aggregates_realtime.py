"""
区域聚合数据API - 实时计算版本
Regional Aggregates API endpoints - Real-time computation

This module replaces precomputed aggregation tables with real-time SQL queries.
Aggregations are computed on-demand from the main village table and semantic_labels.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional, Dict, Any
import sqlite3
import json

from ..dependencies import get_db, execute_query, execute_single
from ..config import DEFAULT_RUN_ID
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/regional", tags=["regional-aggregates"])


def compute_city_aggregates(
    db: sqlite3.Connection,
    city_name: Optional[str] = None,
    run_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    实时计算城市级别聚合数据
    Compute city-level aggregates in real-time

    Uses semantic_indices table for semantic category statistics (already aggregated).
    """
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")

    # Step 1: Get basic aggregations from main table
    query_basic = """
        SELECT
            v.市级 as city,
            COUNT(DISTINCT v.自然村) as total_villages,
            AVG(LENGTH(v.自然村)) as avg_name_length
        FROM 广东省自然村 v
        WHERE 1=1
    """

    params_basic = []

    if city_name is not None:
        query_basic += " AND v.市级 = ?"
        params_basic.append(city_name)

    query_basic += " GROUP BY v.市级"

    basic_results = execute_query(db, query_basic, tuple(params_basic))

    # Step 2: Get semantic category statistics from semantic_indices
    query_semantic = """
        SELECT
            region_name as city,
            category,
            raw_intensity
        FROM semantic_indices
        WHERE region_level = 'city' AND run_id = ?
    """

    params_semantic = [run_id]

    if city_name is not None:
        query_semantic += " AND region_name = ?"
        params_semantic.append(city_name)

    semantic_results = execute_query(db, query_semantic, tuple(params_semantic))

    # Step 3: Merge results
    # Create a dict of city -> semantic stats
    semantic_by_city = {}
    for row in semantic_results:
        city = row['city']
        category = row['category']
        intensity = row['raw_intensity']

        if city not in semantic_by_city:
            semantic_by_city[city] = {}

        semantic_by_city[city][category] = intensity

    # Merge with basic results
    final_results = []
    for row in basic_results:
        city = row['city']
        total = row['total_villages']

        # Add semantic category percentages
        semantic_stats = semantic_by_city.get(city, {})

        row['sem_mountain_pct'] = semantic_stats.get('mountain', 0.0) * 100
        row['sem_water_pct'] = semantic_stats.get('water', 0.0) * 100
        row['sem_settlement_pct'] = semantic_stats.get('settlement', 0.0) * 100
        row['sem_direction_pct'] = semantic_stats.get('direction', 0.0) * 100
        row['sem_clan_pct'] = semantic_stats.get('clan', 0.0) * 100
        row['sem_symbolic_pct'] = semantic_stats.get('symbolic', 0.0) * 100
        row['sem_agriculture_pct'] = semantic_stats.get('agriculture', 0.0) * 100
        row['sem_vegetation_pct'] = semantic_stats.get('vegetation', 0.0) * 100
        row['sem_infrastructure_pct'] = semantic_stats.get('infrastructure', 0.0) * 100

        # Calculate counts from percentages
        row['sem_mountain_count'] = int(row['sem_mountain_pct'] / 100 * total)
        row['sem_water_count'] = int(row['sem_water_pct'] / 100 * total)
        row['sem_settlement_count'] = int(row['sem_settlement_pct'] / 100 * total)
        row['sem_direction_count'] = int(row['sem_direction_pct'] / 100 * total)
        row['sem_clan_count'] = int(row['sem_clan_pct'] / 100 * total)
        row['sem_symbolic_count'] = int(row['sem_symbolic_pct'] / 100 * total)
        row['sem_agriculture_count'] = int(row['sem_agriculture_pct'] / 100 * total)
        row['sem_vegetation_count'] = int(row['sem_vegetation_pct'] / 100 * total)
        row['sem_infrastructure_count'] = int(row['sem_infrastructure_pct'] / 100 * total)

        row['run_id'] = run_id

        final_results.append(row)

    # Sort by total_villages DESC
    final_results.sort(key=lambda x: x['total_villages'], reverse=True)

    return final_results


@router.get("/aggregates/city")
def get_city_aggregates(
    city_name: Optional[str] = Query(None, description="城市名称"),
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取城市级别聚合数据（实时计算）
    Get city-level aggregate statistics (computed in real-time)

    Args:
        city_name: 城市名称（可选）
        run_id: 分析运行ID（可选）

    Returns:
        List[dict]: 城市聚合数据
    """
    results = compute_city_aggregates(db, city_name, run_id)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No city aggregates found"
        )

    return results


def compute_county_aggregates(
    db: sqlite3.Connection,
    county_name: Optional[str] = None,
    city_name: Optional[str] = None,
    run_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    实时计算县区级别聚合数据
    Compute county-level aggregates in real-time

    Uses semantic_indices table for semantic category statistics (already aggregated).
    """
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")

    # Step 1: Get basic aggregations from main table
    query_basic = """
        SELECT
            v.市级 as city,
            v.区县级 as county,
            COUNT(DISTINCT v.自然村) as total_villages,
            AVG(LENGTH(v.自然村)) as avg_name_length
        FROM 广东省自然村 v
        WHERE 1=1
    """

    params_basic = []

    if county_name is not None:
        query_basic += " AND v.区县级 = ?"
        params_basic.append(county_name)

    if city_name is not None:
        query_basic += " AND v.市级 = ?"
        params_basic.append(city_name)

    query_basic += " GROUP BY v.市级, v.区县级"

    basic_results = execute_query(db, query_basic, tuple(params_basic))

    # Step 2: Get semantic category statistics from semantic_indices
    query_semantic = """
        SELECT
            region_name as county,
            category,
            raw_intensity
        FROM semantic_indices
        WHERE region_level = 'county' AND run_id = ?
    """

    params_semantic = [run_id]

    if county_name is not None:
        query_semantic += " AND region_name = ?"
        params_semantic.append(county_name)

    semantic_results = execute_query(db, query_semantic, tuple(params_semantic))

    # Step 3: Merge results
    semantic_by_county = {}
    for row in semantic_results:
        county = row['county']
        category = row['category']
        intensity = row['raw_intensity']

        if county not in semantic_by_county:
            semantic_by_county[county] = {}

        semantic_by_county[county][category] = intensity

    # Merge with basic results
    final_results = []
    for row in basic_results:
        county = row['county']
        total = row['total_villages']

        # Add semantic category percentages
        semantic_stats = semantic_by_county.get(county, {})

        row['sem_mountain_pct'] = semantic_stats.get('mountain', 0.0) * 100
        row['sem_water_pct'] = semantic_stats.get('water', 0.0) * 100
        row['sem_settlement_pct'] = semantic_stats.get('settlement', 0.0) * 100
        row['sem_direction_pct'] = semantic_stats.get('direction', 0.0) * 100
        row['sem_clan_pct'] = semantic_stats.get('clan', 0.0) * 100
        row['sem_symbolic_pct'] = semantic_stats.get('symbolic', 0.0) * 100
        row['sem_agriculture_pct'] = semantic_stats.get('agriculture', 0.0) * 100
        row['sem_vegetation_pct'] = semantic_stats.get('vegetation', 0.0) * 100
        row['sem_infrastructure_pct'] = semantic_stats.get('infrastructure', 0.0) * 100

        # Calculate counts from percentages
        row['sem_mountain_count'] = int(row['sem_mountain_pct'] / 100 * total)
        row['sem_water_count'] = int(row['sem_water_pct'] / 100 * total)
        row['sem_settlement_count'] = int(row['sem_settlement_pct'] / 100 * total)
        row['sem_direction_count'] = int(row['sem_direction_pct'] / 100 * total)
        row['sem_clan_count'] = int(row['sem_clan_pct'] / 100 * total)
        row['sem_symbolic_count'] = int(row['sem_symbolic_pct'] / 100 * total)
        row['sem_agriculture_count'] = int(row['sem_agriculture_pct'] / 100 * total)
        row['sem_vegetation_count'] = int(row['sem_vegetation_pct'] / 100 * total)
        row['sem_infrastructure_count'] = int(row['sem_infrastructure_pct'] / 100 * total)

        row['run_id'] = run_id

        final_results.append(row)

    # Sort by total_villages DESC
    final_results.sort(key=lambda x: x['total_villages'], reverse=True)

    return final_results


@router.get("/aggregates/county")
def get_county_aggregates(
    county_name: Optional[str] = Query(None, description="县区名称"),
    city_name: Optional[str] = Query(None, description="所属城市"),
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取县区级别聚合数据（实时计算）
    Get county-level aggregate statistics (computed in real-time)

    Args:
        county_name: 县区名称（可选）
        city_name: 所属城市（可选）
        run_id: 分析运行ID（可选）

    Returns:
        List[dict]: 县区聚合数据
    """
    results = compute_county_aggregates(db, county_name, city_name, run_id)

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
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取乡镇级别聚合数据（实时计算）
    Get town-level aggregate statistics (computed in real-time)

    Args:
        town_name: 乡镇名称（可选）
        county_name: 所属县区（可选）
        limit: 返回记录数
        run_id: 分析运行ID（可选）

    Returns:
        List[dict]: 乡镇聚合数据
    """
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")

    # Step 1: Get basic aggregations from main table
    query_basic = """
        SELECT
            v.市级 as city,
            v.区县级 as county,
            v.乡镇级 as town,
            COUNT(DISTINCT v.自然村) as total_villages,
            AVG(LENGTH(v.自然村)) as avg_name_length
        FROM 广东省自然村 v
        WHERE 1=1
    """

    params_basic = []

    if town_name is not None:
        query_basic += " AND v.乡镇级 = ?"
        params_basic.append(town_name)

    if county_name is not None:
        query_basic += " AND v.区县级 = ?"
        params_basic.append(county_name)

    query_basic += " GROUP BY v.市级, v.区县级, v.乡镇级 ORDER BY COUNT(DISTINCT v.自然村) DESC LIMIT ?"
    params_basic.append(limit)

    basic_results = execute_query(db, query_basic, tuple(params_basic))

    # Step 2: Get semantic category statistics from semantic_indices
    query_semantic = """
        SELECT
            region_name as town,
            category,
            raw_intensity
        FROM semantic_indices
        WHERE region_level = 'township' AND run_id = ?
    """

    params_semantic = [run_id]

    if town_name is not None:
        query_semantic += " AND region_name = ?"
        params_semantic.append(town_name)

    semantic_results = execute_query(db, query_semantic, tuple(params_semantic))

    # Step 3: Merge results
    semantic_by_town = {}
    for row in semantic_results:
        town = row['town']
        category = row['category']
        intensity = row['raw_intensity']

        if town not in semantic_by_town:
            semantic_by_town[town] = {}

        semantic_by_town[town][category] = intensity

    # Merge with basic results
    final_results = []
    for row in basic_results:
        town = row['town']
        total = row['total_villages']

        # Add semantic category percentages
        semantic_stats = semantic_by_town.get(town, {})

        row['sem_mountain_pct'] = semantic_stats.get('mountain', 0.0) * 100
        row['sem_water_pct'] = semantic_stats.get('water', 0.0) * 100
        row['sem_settlement_pct'] = semantic_stats.get('settlement', 0.0) * 100
        row['sem_direction_pct'] = semantic_stats.get('direction', 0.0) * 100
        row['sem_clan_pct'] = semantic_stats.get('clan', 0.0) * 100
        row['sem_symbolic_pct'] = semantic_stats.get('symbolic', 0.0) * 100
        row['sem_agriculture_pct'] = semantic_stats.get('agriculture', 0.0) * 100
        row['sem_vegetation_pct'] = semantic_stats.get('vegetation', 0.0) * 100
        row['sem_infrastructure_pct'] = semantic_stats.get('infrastructure', 0.0) * 100

        # Calculate counts from percentages
        row['sem_mountain_count'] = int(row['sem_mountain_pct'] / 100 * total)
        row['sem_water_count'] = int(row['sem_water_pct'] / 100 * total)
        row['sem_settlement_count'] = int(row['sem_settlement_pct'] / 100 * total)
        row['sem_direction_count'] = int(row['sem_direction_pct'] / 100 * total)
        row['sem_clan_count'] = int(row['sem_clan_pct'] / 100 * total)
        row['sem_symbolic_count'] = int(row['sem_symbolic_pct'] / 100 * total)
        row['sem_agriculture_count'] = int(row['sem_agriculture_pct'] / 100 * total)
        row['sem_vegetation_count'] = int(row['sem_vegetation_pct'] / 100 * total)
        row['sem_infrastructure_count'] = int(row['sem_infrastructure_pct'] / 100 * total)

        row['run_id'] = run_id

        final_results.append(row)

    if not final_results:
        raise HTTPException(
            status_code=404,
            detail="No town aggregates found"
        )

    return final_results


@router.get("/spatial-aggregates")
def get_region_spatial_aggregates(
    region_level: str = Query(..., description="区域级别（city/county/town）"),
    region_name: Optional[str] = Query(None, description="区域名称"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取区域空间聚合数据（实时计算）
    Get regional spatial aggregate statistics (computed in real-time)

    Args:
        region_level: 区域级别（city/county/town）
        region_name: 区域名称（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 区域空间聚合数据
    """
    # Map region_level to column name
    level_column_map = {
        'city': '市级',
        'county': '区县级',
        'town': '乡镇级'
    }

    if region_level not in level_column_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region_level: {region_level}. Must be one of: city, county, town"
        )

    column_name = level_column_map[region_level]

    query = f"""
        SELECT
            '{region_level}' as region_level,
            v.{column_name} as region_name,
            COUNT(DISTINCT v.自然村) as village_count,
            AVG(sf.local_density) as avg_density,
            AVG(sf.nn_distance) as avg_nn_distance,
            AVG(sf.isolation_score) as avg_isolation_score,
            STDEV(sf.local_density) as spatial_dispersion
        FROM 广东省自然村 v
        LEFT JOIN village_spatial_features sf ON v.自然村 = sf.village_name
        WHERE 1=1
    """

    params = []

    if region_name is not None:
        query += f" AND v.{column_name} = ?"
        params.append(region_name)

    query += f" GROUP BY v.{column_name} ORDER BY village_count DESC LIMIT ?"
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
