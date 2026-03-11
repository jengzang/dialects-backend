"""
小时级和每日级统计路由

提供小时级、每日级的 API 调用统计数据查询接口
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from app.service.logging.stats import hourly_daily_stats


router = APIRouter(prefix="/logs/stats", tags=["日志统计"])


@router.get("/hourly")
async def get_hourly_trend_route(
    hours: int = Query(24, ge=1, le=168)
):
    """
    获取小时级调用趋势

    Args:
        hours: 最近N小时，默认24小时，最多7天（168小时）
    """
    result = hourly_daily_stats.get_hourly_trend(hours=hours)
    return result


@router.get("/daily")
async def get_daily_trend_route(
    days: int = Query(30, ge=1, le=365),
    path: Optional[str] = None
):
    """
    获取每日调用趋势

    Args:
        days: 最近N天，默认30天，最多365天
        path: 指定API路径（可选），不指定则返回所有API的总和
    """
    result = hourly_daily_stats.get_daily_trend(days=days, path=path)
    return result


@router.get("/ranking")
async def get_api_ranking_route(
    date: Optional[str] = None,
    days: Optional[int] = Query(None, ge=1, le=365),
    limit: int = Query(10, ge=1, le=100)
):
    """
    获取 API 排行榜

    Args:
        date: 指定日期（YYYY-MM-DD），与 days 互斥
        days: 最近N天的排行榜，与 date 互斥
        limit: 返回前N个，默认10个，最多100个
    """
    try:
        result = hourly_daily_stats.get_api_ranking(
            date=date,
            days=days,
            limit=limit
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api-history")
async def get_api_history_route(
    path: str,
    days: int = Query(30, ge=1, le=365)
):
    """
    获取指定 API 的历史趋势

    Args:
        path: API路径（必填）
        days: 最近N天，默认30天，最多365天
    """
    result = hourly_daily_stats.get_api_history(path=path, days=days)
    return result
