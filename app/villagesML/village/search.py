"""
村庄搜索API
Village Search API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query, execute_single
from ..config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from ..models import VillageDetail, PaginatedResponse
from ..run_id_manager import get_run_id_manager
from ..schema_runtime import qcolumn, qtable, run_id_analysis_type
from ..schema_keys import C, T

router = APIRouter(prefix="/village/search")


@router.get("", response_model=PaginatedResponse)
def search_villages(
    query: str = Query(..., description="村名关键词（传空字符串或空格查询所有）"),
    city: Optional[str] = Query(None, description="城市过滤"),
    county: Optional[str] = Query(None, description="区县过滤"),
    township: Optional[str] = Query(None, description="乡镇过滤"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    搜索村庄
    Search villages by keyword

    Args:
        query: 村名关键词（传空字符串或空格查询所有）
        city: 城市过滤（可选）
        county: 区县过滤（可选）
        township: 乡镇过滤（可选）
        limit: 返回数量
        offset: 偏移量

    Returns:
        PaginatedResponse: 分页响应，包含总数和数据列表
    """
    # 构建 WHERE 条件
    villages_table = qtable(dbpath, T.VILLAGES)
    village_name_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.NAME)
    city_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.CITY)
    county_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COUNTY)
    township_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.TOWNSHIP)
    longitude_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.LONGITUDE)
    latitude_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.LATITUDE)

    where_conditions = ["1=1"]
    params = []

    # 过滤掉名字为空的记录
    where_conditions.append(f"{village_name_col} IS NOT NULL AND {village_name_col} != ''")

    # 如果 query 不是空字符串或纯空格，添加关键词过滤
    if query.strip():
        where_conditions.append(f"{village_name_col} LIKE ?")
        params.append(f"%{query}%")

    # 区域过滤条件
    if city is not None:
        where_conditions.append(f"{city_col} = ?")
        params.append(city)

    if county is not None:
        where_conditions.append(f"{county_col} = ?")
        params.append(county)

    if township is not None:
        where_conditions.append(f"{township_col} = ?")
        params.append(township)

    where_clause = " AND ".join(where_conditions)

    # 1. 先查询总数
    count_sql = f"""
        SELECT COUNT(*) as total
        FROM {villages_table}
        WHERE {where_clause}
    """
    total_result = execute_query(db, count_sql, tuple(params))
    total = total_result[0]["total"] if total_result else 0

    # 2. 查询当前页数据
    data_sql = f"""
        SELECT
            ROWID as village_id,
            {village_name_col} as village_name,
            {city_col} as city,
            {county_col} as county,
            {township_col} as township,
            CAST({longitude_col} AS REAL) as longitude,
            CAST({latitude_col} AS REAL) as latitude
        FROM {villages_table}
        WHERE {where_clause}
        LIMIT ? OFFSET ?
    """
    data_params = params + [limit, offset]
    results = execute_query(db, data_sql, tuple(data_params))

    # 3. 返回分页响应
    return {
        "total": total,
        "page": (offset // limit) + 1,  # 计算当前页码（从1开始）
        "page_size": limit,
        "data": results
    }


@router.get("/detail", response_model=VillageDetail)
def get_village_detail(
    village_name: str = Query(..., description="村名"),
    city: str = Query(..., description="城市"),
    county: str = Query(..., description="区县"),
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取村庄详情
    Get village detail information

    Args:
        village_name: 村名
        city: 城市
        county: 区县
        run_id: 分析运行ID（留空使用活跃版本）

    Returns:
        VillageDetail: 村庄详情
    """
    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.VILLAGE_FEATURES)
        )
    villages_table = qtable(dbpath, T.VILLAGES)
    village_name_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.NAME)
    city_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.CITY)
    county_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COUNTY)
    township_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.TOWNSHIP)
    longitude_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.LONGITUDE)
    latitude_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.LATITUDE)
    village_features_table = qtable(dbpath, T.VILLAGE_FEATURES)
    village_features_run_id = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.RUN_ID)
    village_features_name = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.VILLAGE_NAME)
    village_features_city = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.CITY)
    village_features_county = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.COUNTY)
    village_features_semantic_tags = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.SEMANTIC_TAGS)
    village_features_suffix = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.SUFFIX)
    village_features_cluster_id = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.CLUSTER_ID)
    village_spatial_features_table = qtable(dbpath, T.VILLAGE_SPATIAL_FEATURES)
    village_spatial_features_village_id = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.VILLAGE_ID)
    village_spatial_features_name = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.VILLAGE_NAME)
    village_spatial_features_city = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.CITY)
    village_spatial_features_county = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.COUNTY)
    village_spatial_features_knn_mean = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.KNN_MEAN_DISTANCE)
    village_spatial_features_local_density = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.LOCAL_DENSITY)
    village_spatial_features_isolation = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.ISOLATION_SCORE)
    village_cluster_assignments_table = qtable(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS)
    village_cluster_assignments_village_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.VILLAGE_ID)
    village_cluster_assignments_run_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.RUN_ID)
    village_cluster_assignments_cluster_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.CLUSTER_ID)
    # 获取基础信息
    basic_query = f"""
        SELECT
            {village_name_col} as village_name,
            {city_col} as city,
            {county_col} as county,
            {township_col} as township,
            CAST({longitude_col} AS REAL) as longitude,
            CAST({latitude_col} AS REAL) as latitude
        FROM {villages_table}
        WHERE {village_name_col} = ? AND {city_col} = ? AND {county_col} = ?
    """
    basic_info = execute_single(db, basic_query, (village_name, city, county))

    if not basic_info:
        raise HTTPException(status_code=404, detail="Village not found")

    # 获取物化特征（如果存在）
    features_query = f"""
        SELECT
            {village_features_semantic_tags} as semantic_tags,
            {village_features_suffix} as suffix,
            {village_features_cluster_id} as cluster_id
        FROM {village_features_table}
        WHERE {village_features_run_id} = ? AND {village_features_name} = ? AND {village_features_city} = ? AND {village_features_county} = ?
    """
    features = execute_single(db, features_query, (run_id, village_name, city, county))

    # 获取空间特征（如果存在）
    spatial_cluster_run_id = get_run_id_manager(dbpath).get_active_run_id(
        run_id_analysis_type(dbpath, T.SPATIAL_CLUSTERS)
    )
    spatial_query = f"""
        SELECT
            vsf.{village_spatial_features_knn_mean} as knn_mean_distance,
            vsf.{village_spatial_features_local_density} as local_density,
            vsf.{village_spatial_features_isolation} as isolation_score,
            vca.{village_cluster_assignments_cluster_id} as spatial_cluster_id
        FROM {village_spatial_features_table} vsf
        LEFT JOIN {village_cluster_assignments_table} vca
            ON vsf.{village_spatial_features_village_id} = vca.{village_cluster_assignments_village_id} AND vca.{village_cluster_assignments_run_id} = ?
        WHERE vsf.{village_spatial_features_name} = ? AND vsf.{village_spatial_features_city} = ? AND vsf.{village_spatial_features_county} = ?
    """
    spatial = execute_single(db, spatial_query, (spatial_cluster_run_id, village_name, city, county))

    # 组装详情
    detail = {
        "basic_info": basic_info,
        "semantic_tags": features.get("semantic_tags", "").split(",") if features else [],
        "suffix": features.get("suffix", "") if features else "",
        "cluster_id": features.get("cluster_id") if features else None,
        "spatial_features": spatial if spatial else None
    }

    return detail
