"""
区域聚合数据API - 实时计算版本
Regional Aggregates API endpoints - Real-time computation

This module replaces precomputed aggregation tables with real-time SQL queries.
Aggregations are computed on-demand from the main village table and semantic_labels.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Body
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import sqlite3
import json
import numpy as np
from scipy.spatial.distance import cosine, euclidean, cityblock
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans, DBSCAN
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

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
        town_name: 乡镇名称（向后兼容，模糊匹配）
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

    # Priority 1: Use hierarchy parameters (exact match)
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

    # Priority 2: Backward compatibility (fuzzy match)
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

    # Priority 1: Use hierarchy parameters (exact match)
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

    # Priority 2: Backward compatibility (fuzzy match)
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
    region_name: Optional[str] = Query(None, description="区域名称（向后兼容）"),
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
        region_name: 区域名称（向后兼容，模糊匹配）
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
    level: str = Query(..., description="区域层级（city/county/township）", pattern="^(city|county|township)$"),
    city: Optional[str] = Query(None, description="市级名称（精确匹配）"),
    county: Optional[str] = Query(None, description="县级名称（精确匹配）"),
    township: Optional[str] = Query(None, description="乡镇级名称（精确匹配）"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取区域语义特征向量（支持层级路径参数以避免重名）
    Get regional semantic feature vectors (supports hierarchical path parameters to avoid duplicates)

    返回区域的9维语义向量和详细的语义类别数据。
    Returns 9-dimensional semantic vectors and detailed semantic category data.

    Args:
        level: 区域层级（必填，city/county/township）
        city: 市级名称（可选，用于精确定位）
        county: 县级名称（可选，用于精确定位）
        township: 乡镇级名称（可选，用于精确定位）
        limit: 返回记录数
        run_id: 分析运行ID（可选）

    Returns:
        List[dict]: 区域特征向量列表，包含：
            - region_name: 区域名称
            - city: 市级名称
            - county: 县级名称（如适用）
            - township: 乡镇级名称（如适用）
            - feature_vector: 9维语义向量
            - village_count: 村庄数量
            - semantic_categories: 语义类别详情（对象）

    Examples:
        # 获取所有市级区域
        GET /api/villages/regional/vectors?level=city&limit=10

        # 获取广州市的数据
        GET /api/villages/regional/vectors?level=city&city=广州市

        # 获取广州市天河区的数据
        GET /api/villages/regional/vectors?level=county&city=广州市&county=天河区

        # 获取广州市天河区龙洞街道的数据（避免与深圳龙岗区龙洞街道混淆）
        GET /api/villages/regional/vectors?level=township&city=广州市&county=天河区&township=龙洞街道
    """
    # 获取 run_id
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")

    # 步骤1: 从 semantic_indices 获取所有符合 level 的区域
    semantic_query = """
        SELECT DISTINCT region_name
        FROM semantic_indices
        WHERE region_level = ? AND run_id = ?
        ORDER BY region_name
        LIMIT ?
    """
    semantic_rows = execute_query(db, semantic_query, (level, run_id, limit * 10))  # 多取一些，后面过滤

    if not semantic_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No regions found for level={level}"
        )

    # 步骤2: 如果提供了 city/county/township 过滤参数，从主表验证并过滤
    if city or county or township:
        # 从主表获取符合条件的 region_name
        filter_query = "SELECT DISTINCT "

        if level == 'city':
            filter_query += "市级 as region_name FROM 广东省自然村 WHERE 1=1"
        elif level == 'county':
            filter_query += "区县级 as region_name FROM 广东省自然村 WHERE 区县级 IS NOT NULL"
        elif level == 'township':
            filter_query += "乡镇级 as region_name FROM 广东省自然村 WHERE 1=1"

        filter_params = []

        if city:
            filter_query += " AND 市级 = ?"
            filter_params.append(city)

        if county:
            filter_query += " AND 区县级 = ?"
            filter_params.append(county)

        if township:
            filter_query += " AND 乡镇级 = ?"
            filter_params.append(township)

        filter_rows = execute_query(db, filter_query, tuple(filter_params))
        allowed_names = {row['region_name'] for row in filter_rows}

        # 过滤 semantic_rows
        semantic_rows = [row for row in semantic_rows if row['region_name'] in allowed_names]

        if not semantic_rows:
            raise HTTPException(
                status_code=404,
                detail=f"No regions found for level={level}, city={city}, county={county}, township={township}"
            )

    # 限制返回数量
    semantic_rows = semantic_rows[:limit]

    # 步骤3: 从主表获取层级信息
    region_names = [row['region_name'] for row in semantic_rows]
    placeholders = ','.join(['?'] * len(region_names))

    hierarchy_query = f"SELECT DISTINCT "

    if level == 'city':
        hierarchy_query += f"市级 as region_name, 市级 as city, NULL as county, NULL as township FROM 广东省自然村 WHERE 市级 IN ({placeholders})"
    elif level == 'county':
        hierarchy_query += f"区县级 as region_name, 市级 as city, 区县级 as county, NULL as township FROM 广东省自然村 WHERE 区县级 IN ({placeholders})"
    elif level == 'township':
        hierarchy_query += f"乡镇级 as region_name, 市级 as city, 区县级 as county, 乡镇级 as township FROM 广东省自然村 WHERE 乡镇级 IN ({placeholders})"

    hierarchy_rows = execute_query(db, hierarchy_query, tuple(region_names))

    # 构建层级信息列表（支持重名区域）
    hierarchy_list = []
    for row in hierarchy_rows:
        hierarchy_list.append({
            'region_name': row['region_name'],
            'city': row['city'],
            'county': row['county'],
            'township': row['township']
        })

    # 步骤4: 使用层级参数精确查询 semantic_indices 表
    results = []
    for hierarchy in hierarchy_list:
        # 使用层级参数精确查询，避免重名问题
        semantic_query = """
            SELECT
                region_name,
                city,
                county,
                township,
                category,
                raw_intensity,
                village_count
            FROM semantic_indices
            WHERE run_id = ? AND region_level = ?
        """
        semantic_params = [run_id, level]

        # 添加层级过滤条件
        if hierarchy['city'] is not None:
            semantic_query += " AND city = ?"
            semantic_params.append(hierarchy['city'])
        if hierarchy['county'] is not None:
            semantic_query += " AND county = ?"
            semantic_params.append(hierarchy['county'])
        elif hierarchy['city'] is not None and level == 'township':
            # Handle 东莞市/中山市 (no county level)
            semantic_query += " AND (county IS NULL OR county = '')"
        if hierarchy['township'] is not None:
            semantic_query += " AND township = ?"
            semantic_params.append(hierarchy['township'])

        semantic_query += " ORDER BY category"

        semantic_rows = execute_query(db, semantic_query, tuple(semantic_params))

        if not semantic_rows or len(semantic_rows) != 9:
            continue  # 跳过不完整的数据

        # 构建语义类别数据
        categories_dict = {}
        village_count = semantic_rows[0]['village_count']
        for row in semantic_rows:
            category = row['category']
            intensity = row['raw_intensity']
            categories_dict[category] = round(intensity, 6)

        # 按字母顺序构建向量
        categories_sorted = sorted(categories_dict.keys())
        feature_vector = [categories_dict[cat] for cat in categories_sorted]

        # 构建结果
        result = {
            'region_name': hierarchy['region_name'],
            'feature_vector': feature_vector,
            'village_count': village_count,
            'semantic_categories': categories_dict
        }

        # 添加层级信息（用于前端显示完整路径）
        if hierarchy['city']:
            result['city'] = hierarchy['city']
        if hierarchy['county']:
            result['county'] = hierarchy['county']
        if hierarchy['township']:
            result['township'] = hierarchy['township']

        results.append(result)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No complete region vectors found"
        )

    return results[:limit]  # 限制返回数量


# ============================================================================
# Vector Comparison API
# ============================================================================

class VectorCompareRequest(BaseModel):
    """区域向量比较请求模型（支持层级路径参数）"""
    level1: str  # "city" | "county" | "township"
    city1: Optional[str] = None
    county1: Optional[str] = None
    township1: Optional[str] = None

    level2: str  # "city" | "county" | "township"
    city2: Optional[str] = None
    county2: Optional[str] = None
    township2: Optional[str] = None

    run_id: Optional[str] = None


class VectorCompareResponse(BaseModel):
    """区域向量比较响应模型"""
    region1_name: str
    level1: str
    city1: Optional[str] = None
    county1: Optional[str] = None
    township1: Optional[str] = None

    region2_name: str
    level2: str
    city2: Optional[str] = None
    county2: Optional[str] = None
    township2: Optional[str] = None

    feature_dimension: int
    categories: List[str]
    cosine_similarity: float
    euclidean_distance: float
    manhattan_distance: float
    vector_diff: List[float]
    region1_vector: List[float]
    region2_vector: List[float]
    run_id: str


def get_semantic_vector_by_hierarchy(
    db: sqlite3.Connection,
    level: str,
    city: Optional[str],
    county: Optional[str],
    township: Optional[str],
    run_id: str
) -> tuple[np.ndarray, List[str], str, dict]:
    """
    通过层级路径参数获取区域的9维语义向量

    Args:
        db: 数据库连接
        level: 区域层级 (city/county/township)
        city: 市级名称
        county: 县级名称
        township: 乡镇级名称
        run_id: 分析运行ID

    Returns:
        (向量数组, 类别列表, 区域名称, 层级信息字典)

    Raises:
        HTTPException: 如果区域不存在或数据不完整
    """
    # 根据层级确定 region_name
    if level == 'city':
        region_name = city
    elif level == 'county':
        region_name = county
    elif level == 'township':
        region_name = township
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level: {level}"
        )

    if not region_name:
        raise HTTPException(
            status_code=400,
            detail=f"Missing region name for level {level}"
        )

    # 使用层级参数精确查询，避免重名问题
    query = """
        SELECT category, raw_intensity
        FROM semantic_indices
        WHERE region_level = ? AND run_id = ?
    """
    params = [level, run_id]

    # 添加层级过滤条件
    if city is not None:
        query += " AND city = ?"
        params.append(city)
    if county is not None:
        query += " AND county = ?"
        params.append(county)
    elif city is not None and level == 'township':
        # Handle 东莞市/中山市 (no county level)
        query += " AND (county IS NULL OR county = '')"
    if township is not None:
        query += " AND township = ?"
        params.append(township)

    query += " ORDER BY category"

    rows = execute_query(db, query, tuple(params))

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Semantic data not found for region '{region_name}' at level '{level}'"
        )

    if len(rows) != 9:
        raise HTTPException(
            status_code=500,
            detail=f"Incomplete data for region '{region_name}': expected 9 categories, got {len(rows)}"
        )

    # 提取类别和强度值
    categories = [row['category'] for row in rows]
    intensities = [row['raw_intensity'] for row in rows]

    # 构建层级信息（用于返回）
    hierarchy_info = {
        'city': city,
        'county': county,
        'township': township
    }

    return np.array(intensities), categories, region_name, hierarchy_info


@router.post("/vectors/compare", response_model=VectorCompareResponse)
def compare_regional_vectors(
    request: VectorCompareRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    比较两个区域的语义特征向量（支持层级路径参数）
    Compare semantic feature vectors between two regions (supports hierarchical path parameters)

    支持同层级和跨层级比较，使用层级路径参数避免重名问题。
    Supports both same-level and cross-level comparison, uses hierarchical path parameters to avoid duplicates.

    Args:
        request: 比较请求参数
        db: 数据库连接

    Returns:
        VectorCompareResponse: 包含相似度指标和原始向量的比较结果

    Examples:
        ```json
        // 同层级比较：广州市 vs 深圳市
        {
            "level1": "city",
            "city1": "广州市",
            "level2": "city",
            "city2": "深圳市"
        }

        // 跨层级比较：广州市 vs 天河区
        {
            "level1": "city",
            "city1": "广州市",
            "level2": "county",
            "city2": "广州市",
            "county2": "天河区"
        }

        // 避免重名：广州天河区龙洞街道 vs 深圳龙岗区龙洞街道
        {
            "level1": "township",
            "city1": "广州市",
            "county1": "天河区",
            "township1": "龙洞街道",
            "level2": "township",
            "city2": "深圳市",
            "county2": "龙岗区",
            "township2": "龙洞街道"
        }
        ```
    """
    # 验证层级参数
    valid_levels = {"city", "county", "township"}
    if request.level1 not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level1: {request.level1}. Must be one of: {valid_levels}"
        )
    if request.level2 not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level2: {request.level2}. Must be one of: {valid_levels}"
        )

    # 获取 run_id
    if request.run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")
    else:
        run_id = request.run_id

    # 获取两个区域的向量（使用层级路径参数）
    vector1, categories1, region1_name, hierarchy1 = get_semantic_vector_by_hierarchy(
        db, request.level1, request.city1, request.county1, request.township1, run_id
    )
    vector2, categories2, region2_name, hierarchy2 = get_semantic_vector_by_hierarchy(
        db, request.level2, request.city2, request.county2, request.township2, run_id
    )

    # 验证类别一致性（应该都是相同的9个类别）
    if categories1 != categories2:
        raise HTTPException(
            status_code=500,
            detail="Category mismatch between regions"
        )

    # 计算相似度和距离指标
    # 1. 余弦相似度 (值越大越相似，范围 0-1)
    cosine_sim = float(1 - cosine(vector1, vector2))

    # 2. 欧氏距离 (值越小越相似)
    euclidean_dist = float(euclidean(vector1, vector2))

    # 3. 曼哈顿距离 (值越小越相似)
    manhattan_dist = float(cityblock(vector1, vector2))

    # 4. 向量差异 (region1 - region2)
    vector_diff = (vector1 - vector2).tolist()

    return VectorCompareResponse(
        region1_name=region1_name,
        level1=request.level1,
        city1=hierarchy1.get('city'),
        county1=hierarchy1.get('county'),
        township1=hierarchy1.get('township'),
        region2_name=region2_name,
        level2=request.level2,
        city2=hierarchy2.get('city'),
        county2=hierarchy2.get('county'),
        township2=hierarchy2.get('township'),
        feature_dimension=9,
        categories=categories1,
        cosine_similarity=round(cosine_sim, 6),
        euclidean_distance=round(euclidean_dist, 6),
        manhattan_distance=round(manhattan_dist, 6),
        vector_diff=[round(v, 6) for v in vector_diff],
        region1_vector=[round(v, 6) for v in vector1.tolist()],
        region2_vector=[round(v, 6) for v in vector2.tolist()],
        run_id=run_id
    )
from .batch_vector_models import (
    RegionSpec, BatchCompareRequest, BatchCompareResponse,
    ReduceRequest, ReduceResponse,
    ClusterRequest, ClusterResponse
)


def get_multiple_vectors(
    db: sqlite3.Connection,
    regions: List[RegionSpec],
    run_id: str
) -> tuple[np.ndarray, List[Dict[str, Any]], List[str]]:
    """
    获取多个区域的向量

    Args:
        db: 数据库连接
        regions: 区域规格列表
        run_id: 分析运行ID

    Returns:
        (向量矩阵, 区域信息列表, 类别列表)
    """
    vectors = []
    region_infos = []
    categories = None

    for region_spec in regions:
        vector, cats, region_name, hierarchy = get_semantic_vector_by_hierarchy(
            db,
            region_spec.level,
            region_spec.city,
            region_spec.county,
            region_spec.township,
            run_id
        )

        vectors.append(vector)
        region_infos.append({
            'region_name': region_name,
            'level': region_spec.level,
            'city': hierarchy.get('city'),
            'county': hierarchy.get('county'),
            'township': hierarchy.get('township')
        })

        if categories is None:
            categories = cats

    return np.array(vectors), region_infos, categories


@router.post("/vectors/compare/batch", response_model=BatchCompareResponse)
def batch_compare_vectors(
    request: BatchCompareRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    批量比较多个区域的向量，返回相似度矩阵
    Batch compare multiple region vectors, returns similarity matrix

    用于热力图可视化。
    Used for heatmap visualization.

    Args:
        request: 批量比较请求参数
        db: 数据库连接

    Returns:
        BatchCompareResponse: 包含相似度矩阵和距离矩阵

    Example:
        {
            "regions": [
                {"level": "city", "city": "广州市"},
                {"level": "city", "city": "深圳市"},
                {"level": "city", "city": "佛山市"}
            ]
        }
    """
    if len(request.regions) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 regions are required for batch comparison"
        )

    if len(request.regions) > 100:
        raise HTTPException(
            status_code=400,
            detail="Maximum 100 regions allowed for batch comparison"
        )

    # 获取 run_id
    if request.run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")
    else:
        run_id = request.run_id

    # 获取所有区域的向量
    vectors, region_infos, categories = get_multiple_vectors(db, request.regions, run_id)

    n = len(vectors)

    # 计算相似度矩阵（余弦相似度）
    similarity_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                similarity_matrix[i][j] = 1.0
            elif i < j:
                sim = 1 - cosine(vectors[i], vectors[j])
                similarity_matrix[i][j] = sim
                similarity_matrix[j][i] = sim

    # 计算距离矩阵（欧氏距离）
    distance_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i < j:
                dist = euclidean(vectors[i], vectors[j])
                distance_matrix[i][j] = dist
                distance_matrix[j][i] = dist

    return BatchCompareResponse(
        regions=region_infos,
        similarity_matrix=[[round(v, 6) for v in row] for row in similarity_matrix.tolist()],
        distance_matrix=[[round(v, 6) for v in row] for row in distance_matrix.tolist()],
        feature_dimension=9,
        categories=categories,
        run_id=run_id
    )


@router.post("/vectors/reduce", response_model=ReduceResponse)
def reduce_vectors(
    request: ReduceRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    向量降维（PCA 或 t-SNE）
    Dimensionality reduction (PCA or t-SNE)

    用于散点图可视化。
    Used for scatter plot visualization.

    Args:
        request: 降维请求参数
        db: 数据库连接

    Returns:
        ReduceResponse: 包含降维后的坐标

    Example:
        {
            "regions": [
                {"level": "city", "city": "广州市"},
                {"level": "city", "city": "深圳市"},
                {"level": "city", "city": "佛山市"}
            ],
            "method": "pca",
            "n_components": 2
        }
    """
    if len(request.regions) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 regions are required for dimensionality reduction"
        )

    if request.n_components not in [2, 3]:
        raise HTTPException(
            status_code=400,
            detail="n_components must be 2 or 3"
        )

    if request.method not in ["pca", "tsne"]:
        raise HTTPException(
            status_code=400,
            detail="method must be 'pca' or 'tsne'"
        )

    # 获取 run_id
    if request.run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")
    else:
        run_id = request.run_id

    # 获取所有区域的向量
    vectors, region_infos, categories = get_multiple_vectors(db, request.regions, run_id)

    # 标准化
    scaler = StandardScaler()
    vectors_scaled = scaler.fit_transform(vectors)

    # 降维
    explained_variance = None
    if request.method == "pca":
        reducer = PCA(n_components=request.n_components)
        coordinates = reducer.fit_transform(vectors_scaled)
        explained_variance = reducer.explained_variance_ratio_.tolist()
    else:  # tsne
        # t-SNE 需要至少 n_components + 1 个样本
        if len(vectors) < request.n_components + 1:
            raise HTTPException(
                status_code=400,
                detail=f"t-SNE requires at least {request.n_components + 1} regions"
            )
        perplexity = min(30, len(vectors) - 1)
        reducer = TSNE(n_components=request.n_components, perplexity=perplexity, random_state=42)
        coordinates = reducer.fit_transform(vectors_scaled)

    return ReduceResponse(
        regions=region_infos,
        coordinates=[[round(v, 6) for v in row] for row in coordinates.tolist()],
        method=request.method,
        n_components=request.n_components,
        explained_variance=[round(v, 6) for v in explained_variance] if explained_variance else None,
        run_id=run_id
    )


@router.post("/vectors/cluster", response_model=ClusterResponse)
def cluster_vectors(
    request: ClusterRequest = Body(...),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    向量聚类（KMeans、DBSCAN 或 GMM）
    Vector clustering (KMeans, DBSCAN, or GMM)

    发现语义相似的区域群组。
    Discover semantically similar region groups.

    Args:
        request: 聚类请求参数
        db: 数据库连接

    Returns:
        ClusterResponse: 包含聚类标签和中心点

    Examples:
        // KMeans
        {
            "regions": [...],
            "method": "kmeans",
            "n_clusters": 3
        }

        // DBSCAN
        {
            "regions": [...],
            "method": "dbscan",
            "eps": 0.5,
            "min_samples": 2
        }

        // GMM
        {
            "regions": [...],
            "method": "gmm",
            "n_clusters": 3
        }
    """
    if len(request.regions) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 regions are required for clustering"
        )

    if request.method not in ["kmeans", "dbscan", "gmm"]:
        raise HTTPException(
            status_code=400,
            detail="method must be 'kmeans', 'dbscan', or 'gmm'"
        )

    # 验证参数
    if request.method in ["kmeans", "gmm"]:
        if request.n_clusters is None:
            raise HTTPException(
                status_code=400,
                detail=f"{request.method} requires n_clusters parameter"
            )
        if request.n_clusters < 2 or request.n_clusters > len(request.regions):
            raise HTTPException(
                status_code=400,
                detail=f"n_clusters must be between 2 and {len(request.regions)}"
            )

    if request.method == "dbscan":
        if request.eps is None or request.min_samples is None:
            raise HTTPException(
                status_code=400,
                detail="dbscan requires eps and min_samples parameters"
            )

    # 获取 run_id
    if request.run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic_indices")
    else:
        run_id = request.run_id

    # 获取所有区域的向量
    vectors, region_infos, categories = get_multiple_vectors(db, request.regions, run_id)

    # 标准化
    scaler = StandardScaler()
    vectors_scaled = scaler.fit_transform(vectors)

    # 聚类
    cluster_centers = None
    if request.method == "kmeans":
        clusterer = KMeans(n_clusters=request.n_clusters, random_state=42)
        labels = clusterer.fit_predict(vectors_scaled)
        # 反标准化中心点
        cluster_centers = scaler.inverse_transform(clusterer.cluster_centers_)
        n_clusters = request.n_clusters

    elif request.method == "dbscan":
        clusterer = DBSCAN(eps=request.eps, min_samples=request.min_samples)
        labels = clusterer.fit_predict(vectors_scaled)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

    else:  # gmm
        clusterer = GaussianMixture(n_components=request.n_clusters, random_state=42)
        labels = clusterer.fit_predict(vectors_scaled)
        # 反标准化中心点
        cluster_centers = scaler.inverse_transform(clusterer.means_)
        n_clusters = request.n_clusters

    return ClusterResponse(
        regions=region_infos,
        labels=labels.tolist(),
        n_clusters=n_clusters,
        cluster_centers=[[round(v, 6) for v in row] for row in cluster_centers.tolist()] if cluster_centers is not None else None,
        method=request.method,
        run_id=run_id
    )
