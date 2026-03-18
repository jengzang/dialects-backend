"""
日志统计路由

提供关键词、API使用、访问量等统计查询接口
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from datetime import datetime
from typing import Optional

from app.service.auth.core.dependencies import get_current_admin_user
from app.service.auth.database.models import User
from app.service.logging.stats import (
    api_stats,
    visit_stats,
    database_stats
)
from app.service.logging.stats import keyword_stats

router = APIRouter(tags=["日志统计"])


# === 关键词统计 ===

@router.get("/keyword/top")
async def get_top_keywords_route(
    limit: int = Query(10, ge=1, le=100),
    days: Optional[int] = Query(None, ge=1)
):
    """获取热门关键词"""
    result = keyword_stats.get_top_keywords(limit=limit, days=days)
    return {"keywords": result}


@router.get("/keyword/search")
async def search_keyword_logs_route(
    keyword: Optional[str] = None,
    user_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200)
):
    """搜索关键词日志"""
    result = keyword_stats.search_keyword_logs(
        keyword=keyword,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size
    )
    return result


# === API 使用统计 ===

@router.get("/api/usage")
async def get_api_usage_route(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
):
    """获取 API 使用统计"""
    result = api_stats.get_api_usage_stats(
        start_time=start_time,
        end_time=end_time
    )
    return result


@router.get("/stats/summary")
async def get_stats_summary_route():
    """获取统计概览"""
    result = api_stats.get_stats_summary()
    return result


@router.get("/stats/fields")
async def get_field_stats_route(
    field: str = Query(..., description="字段名：path, method, user_id, ip_address, status_code")
):
    """获取指定字段的统计信息"""
    try:
        result = api_stats.get_field_stats(field)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# === 访问统计 ===

@router.get("/visits/total")
async def get_total_visits_route():
    """获取总访问量"""
    total = await visit_stats.get_total_visits()
    return {"total_visits": total}


@router.get("/visits/today")
async def get_today_visits_route():
    """获取今日访问量"""
    today = await visit_stats.get_today_visits()
    return {"today_visits": today}


@router.get("/visits/history")
async def get_visit_history_route(
    path: Optional[str] = Query(None, description="筛选特定路径，如 '/', '/admin'"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=10000, description="返回数量"),
    offset: int = Query(0, ge=0, description="分页偏移")
):
    """
    获取历史访问记录（按日期聚合）

    返回每日的访问统计数据，支持分页和筛选
    """
    result = visit_stats.get_visit_history(
        path=path,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )
    return result


@router.get("/visits/by-path")
async def get_visits_by_path_route(
    days: Optional[int] = Query(None, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100)
):
    """按路径统计访问量"""
    result = visit_stats.get_visits_by_path(days=days, limit=limit)
    return {"paths": result, "days": days}


# === 数据库统计（仅管理员）===

@router.get("/database/size")
async def get_database_size_route(
    admin: User = Depends(get_current_admin_user)
):
    """获取数据库大小（仅管理员）"""
    result = database_stats.get_database_size()
    return result

