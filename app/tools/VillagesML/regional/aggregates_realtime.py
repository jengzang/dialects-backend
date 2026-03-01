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

router = APIRouter(prefix="/regional")


def compute_city_aggregates(
    db: sqlite3.Connection,
    city: Optional[str] = None,
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

    if city is not None:
        query_basic += " AND v.市级 = ?"
        params_basic.append(city)

    query_basic += " GROUP BY v.市级"

    basic_results = execute_query(db, query_basic, tuple(params_basic))

    # Step 2: Get semantic category statistics from semantic_indices
    query_semantic = """
        SELECT
            city,
            category,
            raw_intensity
        FROM semantic_indices
        WHERE region_level = 'city' AND run_id = ?
    """

    params_semantic = [run_id]

    if city is not None:
        query_semantic += " AND city = ?"
        params_semantic.append(city)

    semantic_results = execute_query(db, query_semantic, tuple(params_semantic))

    # Step 3: Merge results
    # Create a dict of city -> semantic stats
    semantic_by_city = {}
    for row in semantic_results:
        city_val = row['city']
        category = row['category']
        intensity = row['raw_intensity']

        if city_val not in semantic_by_city:
            semantic_by_city[city_val] = {}

        semantic_by_city[city_val][category] = intensity

    # Merge with basic results
    final_results = []
    for row in basic_results:
        city_val = row['city']
        total = row['total_villages']

        # Add semantic category percentages
        semantic_stats = semantic_by_city.get(city_val, {})

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
    city: Optional[str] = Query(None, description="城市名称"),
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取城市级别聚合数据（实时计算）
    Get city-level aggregate statistics (computed in real-time)

    Args:
        city: 城市名称（可选）
        run_id: 分析运行ID（可选）

    Returns:
        List[dict]: 城市聚合数据
    """
    results = compute_city_aggregates(db, city, run_id)

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
    city: Optional[str] = None,
    county: Optional[str] = None,
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

    # Priority 1: Use hierarchy parameters
    if city is not None:
        query_basic += " AND v.市级 = ?"
        params_basic.append(city)
    if county is not None:
        query_basic += " AND v.区县级 = ?"
        params_basic.append(county)

    # Priority 2: Backward compatibility
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
            city,
            county,
            category,
            raw_intensity
        FROM semantic_indices
        WHERE region_level = 'county' AND run_id = ?
    """

    params_semantic = [run_id]

    # Priority 1: Use hierarchy parameters
    if city is not None:
        query_semantic += " AND city = ?"
        params_semantic.append(city)
    if county is not None:
        query_semantic += " AND county = ?"
        params_semantic.append(county)

    # Priority 2: Backward compatibility
    if county_name is not None:
        query_semantic += " AND (county = ? OR region_name = ?)"
        params_semantic.extend([county_name, county_name])

    semantic_results = execute_query(db, query_semantic, tuple(params_semantic))

    # Step 3: Merge results
    semantic_by_county = {}
    for row in semantic_results:
        key = (row['city'], row['county'])
        category = row['category']
        intensity = row['raw_intensity']

        if key not in semantic_by_county:
            semantic_by_county[key] = {}

        semantic_by_county[key][category] = intensity

    # Merge with basic results
    final_results = []
    for row in basic_results:
        key = (row['city'], row['county'])
        total = row['total_villages']

        # Add semantic category percentages
        semantic_stats = semantic_by_county.get(key, {})

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
    county_name: Optional[str] = Query(None, description="县区名称（向后兼容）"),
    city_name: Optional[str] = Query(None, description="所属城市（向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取县区级别聚合数据（实时计算）
    Get county-level aggregate statistics (computed in real-time)

    Args:
        county_name: 县区名称（向后兼容）
        city_name: 所属城市（向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        run_id: 分析运行ID（可选）

    Returns:
        List[dict]: 县区聚合数据
    """
    results = compute_county_aggregates(db, county_name, city_name, city, county, run_id)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No county aggregates found"
        )

    return results


@router.get("/aggregates/town")
def get_town_aggregates(
    town_name: Optional[str] = Query(None, description="乡镇名称（向后兼容）"),
    county_name: Optional[str] = Query(None, description="所属县区（向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    limit: Optional[int] = Query(None, ge=1, description="返回记录数（不传则返回全部）"),
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取乡镇级别聚合数据（实时计算）
    Get town-level aggregate statistics (computed in real-time)

    Args:
        town_name: 乡镇名称（向后兼容）
        county_name: 所属县区（向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        limit: 返回记录数（不传则返回全部）
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

    # Priority 1: Use hierarchy parameters
    if city is not None:
        query_basic += " AND v.市级 = ?"
        params_basic.append(city)
    if county is not None:
        query_basic += " AND v.区县级 = ?"
        params_basic.append(county)
    elif city is not None:
        # Handle 东莞市/中山市 (no county level)
        query_basic += " AND (v.区县级 IS NULL OR v.区县级 = '')"
    if township is not None:
        query_basic += " AND v.乡镇级 = ?"
        params_basic.append(township)

    # Priority 2: Backward compatibility
    if town_name is not None:
        query_basic += " AND v.乡镇级 = ?"
        params_basic.append(town_name)
    if county_name is not None:
        query_basic += " AND v.区县级 = ?"
        params_basic.append(county_name)

    if limit is not None:
        query_basic += " GROUP BY v.市级, v.区县级, v.乡镇级 ORDER BY COUNT(DISTINCT v.自然村) DESC LIMIT ?"
        params_basic.append(limit)
    else:
        query_basic += " GROUP BY v.市级, v.区县级, v.乡镇级 ORDER BY COUNT(DISTINCT v.自然村) DESC"

    basic_results = execute_query(db, query_basic, tuple(params_basic))

    # Step 2: Get semantic category statistics from semantic_indices
    query_semantic = """
        SELECT
            city,
            county,
            township,
            category,
            raw_intensity
        FROM semantic_indices
        WHERE region_level = 'township' AND run_id = ?
    """

    params_semantic = [run_id]

    # Priority 1: Use hierarchy parameters
    if city is not None:
        query_semantic += " AND city = ?"
        params_semantic.append(city)
    if county is not None:
        query_semantic += " AND county = ?"
        params_semantic.append(county)
    elif city is not None:
        # Handle 东莞市/中山市 (no county level)
        query_semantic += " AND (county IS NULL OR county = '')"
    if township is not None:
        query_semantic += " AND township = ?"
        params_semantic.append(township)

    # Priority 2: Backward compatibility
    if town_name is not None:
        query_semantic += " AND (township = ? OR region_name = ?)"
        params_semantic.extend([town_name, town_name])

    semantic_results = execute_query(db, query_semantic, tuple(params_semantic))

    # Step 3: Merge results
    semantic_by_town = {}
    for row in semantic_results:
        key = (row['city'], row['county'], row['township'])
        category = row['category']
        intensity = row['raw_intensity']

        if key not in semantic_by_town:
            semantic_by_town[key] = {}

        semantic_by_town[key][category] = intensity

    # Merge with basic results
    final_results = []
    for row in basic_results:
        key = (row['city'], row['county'], row['town'])
        total = row['total_villages']

        # Add semantic category percentages
        semantic_stats = semantic_by_town.get(key, {})

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
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    town: Optional[str] = Query(None, description="乡镇级过滤"),
    limit: Optional[int] = Query(None, ge=1, description="返回记录数（不传则返回全部）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取区域空间聚合数据（查询预计算表，毫秒级响应）
    Get regional spatial aggregate statistics from pre-computed table.

    Args:
        region_level: 区域级别（city/county/town）
        region_name: 区域名称（模糊匹配，向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        town: 乡镇级过滤（精确匹配）
        limit: 返回记录数（不传则返回全部）

    Returns:
        List[dict]: 区域空间聚合数据
    """
    if region_level not in ('city', 'county', 'town'):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region_level: {region_level}. Must be one of: city, county, town"
        )

    query = """
        SELECT
            region_level,
            region_name,
            city,
            county,
            town,
            total_villages as village_count,
            avg_local_density as avg_density,
            avg_nn_distance,
            avg_isolation_score,
            spatial_dispersion,
            n_isolated_villages,
            n_spatial_clusters
        FROM region_spatial_aggregates
        WHERE region_level = ?
    """
    params = [region_level]

    # Priority 1: Use hierarchy parameters (exact match)
    if city is not None:
        query += " AND city = ?"
        params.append(city)
    if county is not None:
        query += " AND county = ?"
        params.append(county)
    elif city is not None and region_level == 'town':
        # Handle 东莞市/中山市 (no county level)
        query += " AND (county IS NULL OR county = '')"
    if town is not None:
        query += " AND town = ?"
        params.append(town)

    # Priority 2: Backward compatibility (fuzzy match)
    if region_name is not None:
        query += " AND (city = ? OR county = ? OR town = ? OR region_name = ?)"
        params.extend([region_name, region_name, region_name, region_name])

    query += " ORDER BY village_count DESC"

    if limit is not None:
        query += " LIMIT ?"
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
