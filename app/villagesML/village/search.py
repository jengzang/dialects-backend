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


def _table_columns(db: sqlite3.Connection, table: str) -> set[str]:
    rows = execute_query(db, f"PRAGMA table_info({table})")
    return {row["name"] for row in rows}


def _first_existing_column(
    dbpath: str,
    logical_table: str,
    columns: set[str],
    *logical_columns: str,
) -> str | None:
    for logical_column in logical_columns:
        physical_column = qcolumn(dbpath, logical_table, logical_column)
        if physical_column.strip('"') in columns:
            return physical_column
    return None


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
    village_id: Optional[int] = Query(None, alias="id", description="村庄ROWID"),
    village_name: Optional[str] = Query(None, description="村名"),
    city: Optional[str] = Query(None, description="城市"),
    county: Optional[str] = Query(None, description="区县"),
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
    if village_id is None and (village_name is None or city is None or county is None):
        raise HTTPException(
            status_code=400,
            detail="Provide either id or village_name, city and county"
        )

    if run_id is None:
        run_id = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.VILLAGE_FEATURES)
        )
    villages_table = qtable(dbpath, T.VILLAGES)
    villages_rowid = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.ROWID)
    villages_id = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.VILLAGE_ID)
    village_name_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.NAME)
    city_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.CITY)
    county_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COUNTY)
    township_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.TOWNSHIP)
    longitude_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.LONGITUDE)
    latitude_col = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.LATITUDE)
    village_features_table = qtable(dbpath, T.VILLAGE_FEATURES)
    village_features_run_id = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.RUN_ID)
    village_features_village_id = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.VILLAGE_ID)
    village_features_columns = _table_columns(db, village_features_table)
    village_features_suffix = _first_existing_column(
        dbpath,
        T.VILLAGE_FEATURES,
        village_features_columns,
        C.VILLAGE_FEATURES.SUFFIX,
        C.VILLAGE_FEATURES.SUFFIX_1,
    ) or "NULL"
    village_features_cluster_id = _first_existing_column(
        dbpath,
        T.VILLAGE_FEATURES,
        village_features_columns,
        C.VILLAGE_FEATURES.CLUSTER_ID,
        C.VILLAGE_FEATURES.KMEANS_CLUSTER_ID,
    ) or "NULL"
    semantic_feature_exprs = []
    for category in (
        "agriculture",
        "clan",
        "culture",
        "modifier",
        "settlement",
        "spatial",
        "terrain",
        "vegetation",
        "water",
    ):
        logical_column = f"sem_{category}"
        physical_column = qcolumn(dbpath, T.VILLAGE_FEATURES, logical_column)
        if physical_column.strip('"') in village_features_columns:
            semantic_feature_exprs.append(
                f"CASE WHEN {physical_column} = 1 THEN '{category}' END"
            )
    if semantic_feature_exprs:
        village_features_semantic_tags = (
            "trim("
            + " || ',' || ".join([f"COALESCE({expr}, '')" for expr in semantic_feature_exprs])
            + ", ',')"
        )
    else:
        semantic_tags_column = _first_existing_column(
            dbpath,
            T.VILLAGE_FEATURES,
            village_features_columns,
            C.VILLAGE_FEATURES.SEMANTIC_TAGS,
        )
        village_features_semantic_tags = semantic_tags_column or "''"
    village_spatial_features_table = qtable(dbpath, T.VILLAGE_SPATIAL_FEATURES)
    village_spatial_features_village_id = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.VILLAGE_ID)
    village_spatial_features_columns = _table_columns(db, village_spatial_features_table)
    village_spatial_features_knn_mean = _first_existing_column(
        dbpath,
        T.VILLAGE_SPATIAL_FEATURES,
        village_spatial_features_columns,
        C.VILLAGE_SPATIAL_FEATURES.KNN_MEAN_DISTANCE,
        C.VILLAGE_SPATIAL_FEATURES.NN_DISTANCE_5,
    ) or "NULL"
    village_spatial_features_local_density = _first_existing_column(
        dbpath,
        T.VILLAGE_SPATIAL_FEATURES,
        village_spatial_features_columns,
        C.VILLAGE_SPATIAL_FEATURES.LOCAL_DENSITY,
        C.VILLAGE_SPATIAL_FEATURES.LOCAL_DENSITY_1KM,
    ) or "NULL"
    village_spatial_features_isolation = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.ISOLATION_SCORE)
    village_cluster_assignments_table = qtable(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS)
    village_cluster_assignments_village_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.VILLAGE_ID)
    village_cluster_assignments_run_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.RUN_ID)
    village_cluster_assignments_cluster_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.CLUSTER_ID)

    # 获取基础信息
    basic_where = f"{villages_rowid} = ?"
    basic_params: tuple = (village_id,)
    if village_id is None:
        basic_where = f"{village_name_col} = ? AND {city_col} = ? AND {county_col} = ?"
        basic_params = (village_name, city, county)

    basic_query = f"""
        SELECT
            {villages_rowid} as village_id,
            {village_name_col} as village_name,
            {city_col} as city,
            {county_col} as county,
            {township_col} as township,
            CAST({longitude_col} AS REAL) as longitude,
            CAST({latitude_col} AS REAL) as latitude,
            {villages_id} as village_id_str
        FROM {villages_table}
        WHERE {basic_where}
    """
    basic_info = execute_single(db, basic_query, basic_params)

    if not basic_info:
        raise HTTPException(status_code=404, detail="Village not found")

    materialized_village_id = basic_info["village_id_str"]

    # 获取物化特征（如果存在）
    features_query = f"""
        SELECT
            {village_features_semantic_tags} as semantic_tags,
            {village_features_suffix} as suffix,
            {village_features_cluster_id} as cluster_id
        FROM {village_features_table}
        WHERE {village_features_run_id} = ? AND {village_features_village_id} = ?
    """
    features = execute_single(db, features_query, (run_id, materialized_village_id))

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
        WHERE vsf.{village_spatial_features_village_id} = ?
    """
    spatial = execute_single(db, spatial_query, (spatial_cluster_run_id, materialized_village_id))

    # 组装详情
    detail = {
        "basic_info": basic_info,
        "semantic_tags": [tag for tag in features.get("semantic_tags", "").split(",") if tag] if features else [],
        "suffix": features.get("suffix", "") if features else "",
        "cluster_id": features.get("cluster_id") if features else None,
        "spatial_features": spatial if spatial else None
    }

    return detail
