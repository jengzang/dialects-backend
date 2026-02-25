"""
村庄搜索API
Village Search API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single
from ..config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, DEFAULT_RUN_ID
from ..models import VillageBasic, VillageDetail, PaginatedResponse

router = APIRouter(prefix="/village/search")


@router.get("", response_model=PaginatedResponse)
def search_villages(
    query: str = Query(..., description="村名关键词（传空字符串或空格查询所有）"),
    city: Optional[str] = Query(None, description="城市过滤"),
    county: Optional[str] = Query(None, description="区县过滤"),
    township: Optional[str] = Query(None, description="乡镇过滤"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: sqlite3.Connection = Depends(get_db)
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
    where_conditions = ["1=1"]
    params = []

    # 过滤掉名字为空的记录
    where_conditions.append("自然村_规范名 IS NOT NULL AND 自然村_规范名 != ''")

    # 如果 query 不是空字符串或纯空格，添加关键词过滤
    if query.strip():
        where_conditions.append("自然村_规范名 LIKE ?")
        params.append(f"%{query}%")

    # 区域过滤条件
    if city is not None:
        where_conditions.append("市级 = ?")
        params.append(city)

    if county is not None:
        where_conditions.append("区县级 = ?")
        params.append(county)

    if township is not None:
        where_conditions.append("乡镇级 = ?")
        params.append(township)

    where_clause = " AND ".join(where_conditions)

    # 1. 先查询总数
    count_sql = f"""
        SELECT COUNT(*) as total
        FROM 广东省自然村_预处理
        WHERE {where_clause}
    """
    total_result = execute_query(db, count_sql, tuple(params))
    total = total_result[0]["total"] if total_result else 0

    # 2. 查询当前页数据
    data_sql = f"""
        SELECT
            ROWID as village_id,
            自然村_规范名 as village_name,
            市级 as city,
            区县级 as county,
            乡镇级 as township,
            CAST(longitude AS REAL) as longitude,
            CAST(latitude AS REAL) as latitude
        FROM 广东省自然村_预处理
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
    run_id: str = Query(DEFAULT_RUN_ID, description="分析运行ID"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取村庄详情
    Get village detail information

    Args:
        village_name: 村名
        city: 城市
        county: 区县
        run_id: 分析运行ID

    Returns:
        VillageDetail: 村庄详情
    """
    # 获取基础信息
    basic_query = """
        SELECT
            自然村_规范名 as village_name,
            市级 as city,
            区县级 as county,
            乡镇级 as township,
            CAST(longitude AS REAL) as longitude,
            CAST(latitude AS REAL) as latitude
        FROM 广东省自然村_预处理
        WHERE 自然村_规范名 = ? AND 市级 = ? AND 区县级 = ?
    """
    basic_info = execute_single(db, basic_query, (village_name, city, county))

    if not basic_info:
        raise HTTPException(status_code=404, detail="Village not found")

    # 获取物化特征（如果存在）
    features_query = """
        SELECT
            semantic_tags,
            suffix,
            cluster_id
        FROM village_features
        WHERE run_id = ? AND village_name = ? AND city = ? AND county = ?
    """
    features = execute_single(db, features_query, (run_id, village_name, city, county))

    # 获取空间特征（如果存在）
    spatial_query = """
        SELECT
            vsf.knn_mean_distance,
            vsf.local_density,
            vsf.isolation_score,
            vca.cluster_id as spatial_cluster_id
        FROM village_spatial_features vsf
        LEFT JOIN village_cluster_assignments vca
            ON vsf.village_id = vca.village_id AND vca.run_id = 'spatial_eps_20'
        WHERE vsf.village_name = ? AND vsf.city = ? AND vsf.county = ?
    """
    spatial = execute_single(db, spatial_query, (village_name, city, county))

    # 组装详情
    detail = {
        "basic_info": basic_info,
        "semantic_tags": features.get("semantic_tags", "").split(",") if features else [],
        "suffix": features.get("suffix", "") if features else "",
        "cluster_id": features.get("cluster_id") if features else None,
        "spatial_features": spatial if spatial else None
    }

    return detail
