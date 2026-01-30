# routes/logs_stats.py
"""
日志统计 API
提供日志数据的查询和统计功能
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, desc, and_
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin_user
from app.auth.models import User
from app.logs.database import get_db
from app.logs.models import ApiKeywordLog, ApiStatistics, ApiVisitLog
router = APIRouter()


# ============ 查询 API ============

@router.get("/keyword/top")
async def get_top_keywords(
    field: Optional[str] = Query(None, description="筛选特定字段，如 'locations'、'regions'"),
    date: Optional[str] = Query(None, description="日期筛选 YYYY-MM-DD，不填则返回总计"),
    limit: int = Query(20, ge=1, le=100, description="返回前 N 个关键词"),
    db: Session = Depends(get_db)
):
    """
    获取最常用的关键词

    示例：
    - /api/logs/keyword/top - 所有字段的总计 Top 20
    - /api/logs/keyword/top?field=locations&limit=10 - locations 字段的总计 Top 10
    - /api/logs/keyword/top?date=2025-01-21 - 指定日期的所有字段 Top 20
    """
    stat_type = "keyword_daily" if date else "keyword_total"
    date_filter = datetime.strptime(date, "%Y-%m-%d") if date else None

    query = db.query(
        ApiStatistics.category,
        ApiStatistics.item,
        ApiStatistics.count
    ).filter(ApiStatistics.stat_type == stat_type)

    if date_filter:
        query = query.filter(func.date(ApiStatistics.date) == date_filter.date())
    else:
        query = query.filter(ApiStatistics.date.is_(None))

    if field:
        query = query.filter(ApiStatistics.category == field)

    results = query.order_by(desc(ApiStatistics.count)).limit(limit).all()

    return {
        "stat_type": stat_type,
        "date": date,
        "field_filter": field,
        "total_items": len(results),
        "data": [
            {
                "field": row.category,
                "keyword": row.item,
                "count": row.count
            }
            for row in results
        ]
    }


@router.get("/api/usage")
async def get_api_usage(
    date: Optional[str] = Query(None, description="日期筛选 YYYY-MM-DD"),
    limit: int = Query(20, ge=1, le=100, description="返回前 N 个 API"),
    db: Session = Depends(get_db)
):
    """
    获取 API 调用次数统计

    示例：
    - /api/logs/api/usage - 总计 Top 20
    - /api/logs/api/usage?date=2025-01-21 - 指定日期 Top 20
    """
    stat_type = "usage_daily" if date else "usage_total"
    date_filter = datetime.strptime(date, "%Y-%m-%d") if date else None

    query = db.query(
        ApiStatistics.item,
        ApiStatistics.count
    ).filter(
        ApiStatistics.stat_type == stat_type,
        ApiStatistics.category == "path"
    )

    if date_filter:
        query = query.filter(func.date(ApiStatistics.date) == date_filter.date())
    else:
        query = query.filter(ApiStatistics.date.is_(None))

    results = query.order_by(desc(ApiStatistics.count)).limit(limit).all()

    total_calls = sum(row.count for row in results)

    return {
        "stat_type": stat_type,
        "date": date,
        "total_api_calls": total_calls,
        "total_endpoints": len(results),
        "data": [
            {
                "path": row.item,
                "count": row.count,
                "percentage": round(row.count / total_calls * 100, 2) if total_calls > 0 else 0
            }
            for row in results
        ]
    }


@router.get("/keyword/search")
async def search_keyword_logs(
    field: Optional[str] = Query(None, description="字段名"),
    value: Optional[str] = Query(None, description="关键词值（模糊匹配）"),
    path: Optional[str] = Query(None, description="API 路径（模糊匹配）"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    db: Session = Depends(get_db)
):
    """
    搜索关键词日志

    示例：
    - /api/logs/keyword/search?field=locations&value=广州
    - /api/logs/keyword/search?path=/api/phonology&start_date=2025-01-20
    """
    query = db.query(ApiKeywordLog)

    if field:
        query = query.filter(ApiKeywordLog.field == field)

    if value:
        query = query.filter(ApiKeywordLog.value.like(f"%{value}%"))

    if path:
        query = query.filter(ApiKeywordLog.path.like(f"%{path}%"))

    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(ApiKeywordLog.timestamp >= start)

    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(ApiKeywordLog.timestamp < end)

    total = query.count()
    results = query.order_by(desc(ApiKeywordLog.timestamp)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "path": log.path,
                "field": log.field,
                "value": log.value
            }
            for log in results
        ]
    }


@router.get("/stats/summary")
async def get_stats_summary(
    days: int = Query(7, ge=1, le=90, description="统计最近 N 天"),
    db: Session = Depends(get_db)
):
    """
    获取统计概览

    返回：
    - 总日志数
    - 最近 N 天的趋势
    - Top API
    - Top 关键词
    """
    start_date = datetime.now() - timedelta(days=days)

    # 总日志数
    total_logs = db.query(func.count(ApiKeywordLog.id)).scalar()

    # 最近 N 天的日志数
    recent_logs = db.query(func.count(ApiKeywordLog.id)).filter(
        ApiKeywordLog.timestamp >= start_date
    ).scalar()

    # 最近 N 天每日趋势
    daily_trend = db.query(
        func.date(ApiKeywordLog.timestamp).label('date'),
        func.count(ApiKeywordLog.id).label('count')
    ).filter(
        ApiKeywordLog.timestamp >= start_date
    ).group_by(func.date(ApiKeywordLog.timestamp)).order_by('date').all()

    # Top 5 API（总计）
    top_apis = db.query(
        ApiStatistics.item,
        ApiStatistics.count
    ).filter(
        ApiStatistics.stat_type == "usage_total",
        ApiStatistics.category == "path"
    ).order_by(desc(ApiStatistics.count)).limit(5).all()

    # Top 5 关键词（总计）
    top_keywords = db.query(
        ApiStatistics.category,
        ApiStatistics.item,
        ApiStatistics.count
    ).filter(
        ApiStatistics.stat_type == "keyword_total"
    ).order_by(desc(ApiStatistics.count)).limit(5).all()

    return {
        "overview": {
            "total_logs": total_logs,
            "recent_logs": recent_logs,
            "days": days
        },
        "daily_trend": [
            {
                "date": str(row.date),
                "count": row.count
            }
            for row in daily_trend
        ],
        "top_apis": [
            {
                "path": row.item,
                "count": row.count
            }
            for row in top_apis
        ],
        "top_keywords": [
            {
                "field": row.category,
                "keyword": row.item,
                "count": row.count
            }
            for row in top_keywords
        ]
    }


@router.get("/stats/fields")
async def get_field_statistics(
    date: Optional[str] = Query(None, description="日期筛选 YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    获取各字段的统计分布

    返回每个字段的关键词数量和调用次数
    """
    stat_type = "keyword_daily" if date else "keyword_total"
    date_filter = datetime.strptime(date, "%Y-%m-%d") if date else None

    query = db.query(
        ApiStatistics.category,
        func.count(ApiStatistics.item).label('unique_keywords'),
        func.sum(ApiStatistics.count).label('total_calls')
    ).filter(ApiStatistics.stat_type == stat_type)

    if date_filter:
        query = query.filter(func.date(ApiStatistics.date) == date_filter.date())
    else:
        query = query.filter(ApiStatistics.date.is_(None))

    results = query.group_by(ApiStatistics.category).order_by(desc('total_calls')).all()

    return {
        "date": date,
        "data": [
            {
                "field": row.category,
                "unique_keywords": row.unique_keywords,
                "total_calls": row.total_calls
            }
            for row in results
        ]
    }


# ============ 访问统计 API（HTML 页面访问）============

@router.get("/visits/total")
async def get_total_visits(
    db: Session = Depends(get_db)
):
    """
    获取总访问次数（所有时间）

    返回所有 HTML 页面的总访问次数

    示例：
    - /logs/visits/total - 返回所有时间的总访问次数
    """
    # 查询 date=NULL 的记录（总计）
    results = db.query(ApiVisitLog).filter(ApiVisitLog.date.is_(None)).all()

    total = sum(r.count for r in results)

    return {
        "total_visits": total,
        "description": "所有时间的总访问次数",
        "by_path": [
            {
                "path": r.path,
                "count": r.count
            }
            for r in results
        ]
    }


@router.get("/visits/today")
async def get_today_visits(
    db: Session = Depends(get_db)
):
    """
    获取今日访问次数

    示例：
    - /logs/visits/today - 返回今天的访问次数
    """
    today = datetime.now().date()
    results = db.query(ApiVisitLog).filter(
        func.date(ApiVisitLog.date) == today
    ).all()

    total = sum(r.count for r in results)

    return {
        "today_visits": total,
        "date": str(today),
        "description": "今日访问次数",
        "by_path": [
            {
                "path": r.path,
                "count": r.count
            }
            for r in results
        ]
    }


@router.get("/visits/history")
async def get_visit_history(
    path: Optional[str] = Query(None, description="筛选特定路径，如 '/', '/admin'"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=10000, description="返回数量"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    db: Session = Depends(get_db)
):
    """
    获取历史访问记录（按日期聚合）

    返回每日的访问统计数据，支持分页和筛选

    示例：
    - /logs/visits/history - 返回最近100天的访问统计
    - /logs/visits/history?path=/ - 筛选特定路径
    - /logs/visits/history?start_date=2025-01-01&end_date=2025-01-31 - 筛选时间范围
    """
    query = db.query(ApiVisitLog).filter(ApiVisitLog.date.isnot(None))

    if path:
        query = query.filter(ApiVisitLog.path == path)

    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        query = query.filter(func.date(ApiVisitLog.date) >= start)

    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        query = query.filter(func.date(ApiVisitLog.date) <= end)

    total = query.count()
    results = query.order_by(desc(ApiVisitLog.date)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": [
            {
                "id": log.id,
                "path": log.path,
                "date": log.date.strftime("%Y-%m-%d") if log.date else None,
                "count": log.count,
                "updated_at": log.updated_at.isoformat() if log.updated_at else None
            }
            for log in results
        ]
    }


@router.get("/visits/by-path")
async def get_visits_by_path(
    date: Optional[str] = Query(None, description="日期筛选 YYYY-MM-DD，不填则返回总计"),
    limit: int = Query(20, ge=1, le=100, description="返回前 N 个路径"),
    db: Session = Depends(get_db)
):
    """
    按路径统计访问次数

    示例：
    - /logs/visits/by-path - 所有时间的 Top 20 路径
    - /logs/visits/by-path?date=2025-01-21 - 今日 Top 20 路径
    """
    if date:
        date_filter = datetime.strptime(date, "%Y-%m-%d").date()
        results = db.query(ApiVisitLog).filter(
            func.date(ApiVisitLog.date) == date_filter
        ).order_by(desc(ApiVisitLog.count)).limit(limit).all()
    else:
        # 查询总计（date=NULL）
        results = db.query(ApiVisitLog).filter(
            ApiVisitLog.date.is_(None)
        ).order_by(desc(ApiVisitLog.count)).limit(limit).all()

    total_visits = sum(r.count for r in results)

    return {
        "date": date,
        "total_paths": len(results),
        "total_visits": total_visits,
        "data": [
            {
                "path": row.path,
                "count": row.count,
                "percentage": round(row.count / total_visits * 100, 2) if total_visits > 0 else 0
            }
            for row in results
        ]
    }


# ============ 管理 API（需要管理员权限）============

# @router.delete("/cleanup")
# async def cleanup_old_logs(
#     days: int = Query(30, ge=7, le=365, description="删除 N 天前的日志"),
#     dry_run: bool = Query(False, description="试运行，不实际删除"),
#     current_user: User = Depends(get_current_admin_user),
#     db: Session = Depends(get_db)
# ):
#     """
#     清理旧日志（管理员）
#
#     删除指定天数前的关键词日志和每日统计
#     """
#     cutoff_date = datetime.now() - timedelta(days=days)
#
#     # 统计将被删除的数据
#     keyword_count = db.query(func.count(ApiKeywordLog.id)).filter(
#         ApiKeywordLog.timestamp < cutoff_date
#     ).scalar()
#
#     daily_stats_count = db.query(func.count(ApiStatistics.id)).filter(
#         and_(
#             ApiStatistics.stat_type.in_(["keyword_daily", "usage_daily"]),
#             ApiStatistics.date < cutoff_date
#         )
#     ).scalar()
#
#     if dry_run:
#         return {
#             "dry_run": True,
#             "cutoff_date": cutoff_date.isoformat(),
#             "would_delete": {
#                 "keyword_logs": keyword_count,
#                 "daily_statistics": daily_stats_count
#             }
#         }
#
#     # 实际删除
#     try:
#         deleted_keywords = db.query(ApiKeywordLog).filter(
#             ApiKeywordLog.timestamp < cutoff_date
#         ).delete()
#
#         deleted_stats = db.query(ApiStatistics).filter(
#             and_(
#                 ApiStatistics.stat_type.in_(["keyword_daily", "usage_daily"]),
#                 ApiStatistics.date < cutoff_date
#             )
#         ).delete()
#
#         db.commit()
#
#         return {
#             "success": True,
#             "cutoff_date": cutoff_date.isoformat(),
#             "deleted": {
#                 "keyword_logs": deleted_keywords,
#                 "daily_statistics": deleted_stats
#             }
#         }
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")
#
#
# @router.post("/aggregate")
# async def trigger_aggregation(
#     current_user: User = Depends(get_current_admin_user),
#     db: Session = Depends(get_db)
# ):
#     """
#     手动触发关键词统计聚合（管理员）
#
#     重新聚合所有关键词统计
#     """
#     try:
#         # 清空现有关键词统计
#         db.query(ApiStatistics).filter(
#             ApiStatistics.stat_type.in_(["keyword_total", "keyword_daily"])
#         ).delete()
#
#         # 聚合总计
#         db.execute("""
#             INSERT INTO api_statistics (stat_type, date, category, item, count, updated_at)
#             SELECT
#                 'keyword_total' as stat_type,
#                 NULL as date,
#                 field as category,
#                 value as item,
#                 COUNT(*) as count,
#                 datetime('now') as updated_at
#             FROM api_keyword_log
#             GROUP BY field, value
#         """)
#
#         # 聚合每日统计
#         db.execute("""
#             INSERT INTO api_statistics (stat_type, date, category, item, count, updated_at)
#             SELECT
#                 'keyword_daily' as stat_type,
#                 DATE(timestamp) as date,
#                 field as category,
#                 value as item,
#                 COUNT(*) as count,
#                 datetime('now') as updated_at
#             FROM api_keyword_log
#             GROUP BY DATE(timestamp), field, value
#         """)
#
#         db.commit()
#
#         # 统计结果
#         keyword_total = db.query(func.count(ApiStatistics.id)).filter(
#             ApiStatistics.stat_type == "keyword_total"
#         ).scalar()
#
#         keyword_daily = db.query(func.count(ApiStatistics.id)).filter(
#             ApiStatistics.stat_type == "keyword_daily"
#         ).scalar()
#
#         return {
#             "success": True,
#             "aggregated": {
#                 "keyword_total": keyword_total,
#                 "keyword_daily": keyword_daily
#             }
#         }
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"聚合失败: {str(e)}")


@router.get("/database/size")
async def get_database_size(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    获取数据库大小和统计信息（管理员）
    """
    import os
    from common.config import LOGS_DATABASE_PATH

    # 文件大小
    db_size = os.path.getsize(LOGS_DATABASE_PATH) if os.path.exists(LOGS_DATABASE_PATH) else 0

    # 各表记录数
    keyword_log_count = db.query(func.count(ApiKeywordLog.id)).scalar()
    statistics_count = db.query(func.count(ApiStatistics.id)).scalar()

    # 各类型统计数
    stat_breakdown = db.query(
        ApiStatistics.stat_type,
        func.count(ApiStatistics.id).label('count')
    ).group_by(ApiStatistics.stat_type).all()

    return {
        "database_path": LOGS_DATABASE_PATH,
        "file_size_bytes": db_size,
        "file_size_mb": round(db_size / 1024 / 1024, 2),
        "tables": {
            "api_keyword_log": keyword_log_count,
            "api_statistics": statistics_count
        },
        "statistics_breakdown": {
            row.stat_type: row.count
            for row in stat_breakdown
        }
    }
