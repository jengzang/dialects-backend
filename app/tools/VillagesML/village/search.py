"""
村庄搜索API
Village Search API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single
from ..config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, DEFAULT_RUN_ID
from ..models import VillageBasic, VillageDetail

router = APIRouter(prefix="/village/search", tags=["village"])


@router.get("", response_model=List[VillageBasic])
def search_villages(
    query: str = Query(..., description="村名关键词", min_length=1),
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
        query: 村名关键词
        city: 城市过滤（可选）
        county: 区县过滤（可选）
        township: 乡镇过滤（可选）
        limit: 返回数量
        offset: 偏移量

    Returns:
        List[VillageBasic]: 村庄基础信息列表
    """
    # 构建查询
    sql = """
        SELECT
            ROWID as village_id,
            自然村 as village_name,
            市级 as city,
            区县级 as county,
            乡镇级 as township,
            CAST(longitude AS REAL) as longitude,
            CAST(latitude AS REAL) as latitude
        FROM 广东省自然村
        WHERE 自然村 LIKE ?
    """
    params = [f"%{query}%"]

    # 现场过滤：区域条件
    if city is not None:
        sql += " AND 市级 = ?"
        params.append(city)

    if county is not None:
        sql += " AND 区县级 = ?"
        params.append(county)

    if township is not None:
        sql += " AND 乡镇级 = ?"
        params.append(township)

    # 现场分页
    sql += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    results = execute_query(db, sql, tuple(params))

    return results


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
            自然村 as village_name,
            市级 as city,
            区县级 as county,
            乡镇级 as township,
            CAST(longitude AS REAL) as longitude,
            CAST(latitude AS REAL) as latitude
        FROM 广东省自然村
        WHERE 自然村 = ? AND 市级 = ? AND 区县级 = ?
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
            knn_mean_distance,
            local_density,
            isolation_score
        FROM village_spatial_features
        WHERE run_id = ? AND village_name = ? AND city = ? AND county = ?
    """
    spatial = execute_single(db, spatial_query, (run_id, village_name, city, county))

    # 组装详情
    detail = {
        "basic_info": basic_info,
        "semantic_tags": features.get("semantic_tags", "").split(",") if features else [],
        "suffix": features.get("suffix", "") if features else "",
        "cluster_id": features.get("cluster_id") if features else None,
        "spatial_features": spatial if spatial else None
    }

    return detail
