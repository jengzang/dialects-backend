from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc
from app.auth import models
from app.auth.database import get_db
from typing import Optional, Literal

router = APIRouter()

# 获取用户的 API 使用统计，通过 username 或 email 查找
@router.get("/api-summary")
def get_api_usage_summary(query: str, db: Session = Depends(get_db)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 返回该用户的 API 使用统计
    return db.query(models.ApiUsageSummary).filter(models.ApiUsageSummary.user_id == user.id).all()


@router.get("/api-detail")
def get_user_api_usage(query: str, db: Session = Depends(get_db)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    api_logs = db.query(models.ApiUsageLog).filter(
        models.ApiUsageLog.user_id == user.id,
        models.ApiUsageLog.path != '/login'
    ).all()

    api_logs.sort(key=lambda log: log.called_at, reverse=True)

    # 返回 API 使用记录
    return {"user": user.username, "api_logs": api_logs}


# 通过查询日志数据获取指定字段（增强版：支持搜索、排序、统计）
@router.get("/api-usage")
def get_all_api_usage(
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(50, ge=1, le=500, description="分页限制"),
    search: Optional[str] = Query(None, description="搜索关键词（匹配 user/ip/path/os/browser）"),
    sort_by: Optional[Literal["user", "ip", "path", "duration", "os", "browser", "called_at", "request_size", "response_size"]] = Query(None, description="排序字段"),
    sort_order: Optional[Literal["asc", "desc"]] = Query("desc", description="排序方向"),
    include_stats: bool = Query(False, description="是否返回全局统计信息"),
    db: Session = Depends(get_db)
):
    """
    获取 API 使用日志（增强版）

    支持功能：
    - 分页：skip, limit
    - 搜索：search（匹配 user/ip/path/os/browser）
    - 排序：sort_by, sort_order
    - 统计：include_stats（返回全局统计信息）
    """
    # 基础查询
    base_query = db.query(
        models.ApiUsageLog,
        models.User.username
    ).outerjoin(
        models.User,
        models.ApiUsageLog.user_id == models.User.id
    ).filter(
        models.ApiUsageLog.path != '/login'
    )

    # 搜索过滤
    if search:
        search_pattern = f"%{search}%"
        base_query = base_query.filter(
            or_(
                models.User.username.like(search_pattern),
                models.ApiUsageLog.ip.like(search_pattern),
                models.ApiUsageLog.path.like(search_pattern),
                models.ApiUsageLog.user_agent.like(search_pattern)
            )
        )

    # 排序
    if sort_by:
        # 映射前端字段到数据库字段
        sort_field_map = {
            "user": models.User.username,
            "ip": models.ApiUsageLog.ip,
            "path": models.ApiUsageLog.path,
            "duration": models.ApiUsageLog.duration,
            "called_at": models.ApiUsageLog.called_at,
            "request_size": models.ApiUsageLog.request_size,
            "response_size": models.ApiUsageLog.response_size,
        }

        if sort_by in sort_field_map:
            sort_field = sort_field_map[sort_by]
            if sort_order == "asc":
                base_query = base_query.order_by(asc(sort_field))
            else:
                base_query = base_query.order_by(desc(sort_field))
        else:
            # os 和 browser 需要特殊处理（从 user_agent 提取）
            # 默认按时间倒序
            base_query = base_query.order_by(desc(models.ApiUsageLog.called_at))
    else:
        # 默认按时间倒序
        base_query = base_query.order_by(desc(models.ApiUsageLog.called_at))

    # 获取总数（搜索后的）
    total = base_query.count()

    # 应用分页
    logs = base_query.offset(skip).limit(limit).all()

    # 构建结果
    result = []
    for log, username in logs:
        os, browser = extract_device_info(log.user_agent)
        result.append({
            "user": username or '',
            "ip": log.ip,
            "path": log.path,
            "duration": log.duration,
            "os": os,
            "browser": browser,
            "called_at": log.called_at.strftime("%Y-%m-%d %H:%M:%S"),
            "request_size": log.request_size,
            "response_size": log.response_size,
        })

    # 基础响应
    response = {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": result
    }

    # 如果需要统计信息
    if include_stats:
        # 构建统计查询（基于相同的搜索条件）
        stats_query = db.query(models.ApiUsageLog).outerjoin(
            models.User,
            models.ApiUsageLog.user_id == models.User.id
        ).filter(
            models.ApiUsageLog.path != '/login'
        )

        if search:
            search_pattern = f"%{search}%"
            stats_query = stats_query.filter(
                or_(
                    models.User.username.like(search_pattern),
                    models.ApiUsageLog.ip.like(search_pattern),
                    models.ApiUsageLog.path.like(search_pattern),
                    models.ApiUsageLog.user_agent.like(search_pattern)
                )
            )

        # 全局统计
        summary = stats_query.with_entities(
            func.count(models.ApiUsageLog.id).label('total_calls'),
            func.count(func.distinct(models.ApiUsageLog.user_id)).label('unique_users'),
            func.count(func.distinct(models.ApiUsageLog.ip)).label('unique_ips'),
            func.count(func.distinct(models.ApiUsageLog.path)).label('unique_paths'),
            func.sum(models.ApiUsageLog.duration).label('total_duration'),
            func.sum(models.ApiUsageLog.request_size).label('total_upload'),
            func.sum(models.ApiUsageLog.response_size).label('total_download')
        ).first()

        # 用户统计（Top 10）
        user_stats = stats_query.with_entities(
            models.User.username,
            func.count(models.ApiUsageLog.id).label('call_count'),
            func.sum(models.ApiUsageLog.duration).label('total_duration'),
            func.sum(models.ApiUsageLog.request_size).label('total_upload'),
            func.sum(models.ApiUsageLog.response_size).label('total_download')
        ).filter(
            models.User.username.isnot(None)
        ).group_by(
            models.User.username
        ).order_by(
            desc('total_duration')
        ).limit(10).all()

        # IP 统计（Top 10）
        ip_stats = stats_query.with_entities(
            models.ApiUsageLog.ip,
            func.count(models.ApiUsageLog.id).label('call_count'),
            func.sum(models.ApiUsageLog.duration).label('total_duration'),
            func.sum(models.ApiUsageLog.request_size).label('total_upload'),
            func.sum(models.ApiUsageLog.response_size).label('total_download')
        ).group_by(
            models.ApiUsageLog.ip
        ).order_by(
            desc('total_duration')
        ).limit(10).all()

        # 路径统计（Top 10）
        path_stats = stats_query.with_entities(
            models.ApiUsageLog.path,
            func.count(models.ApiUsageLog.id).label('call_count'),
            func.sum(models.ApiUsageLog.duration).label('total_duration'),
            func.sum(models.ApiUsageLog.request_size).label('total_upload'),
            func.sum(models.ApiUsageLog.response_size).label('total_download')
        ).group_by(
            models.ApiUsageLog.path
        ).order_by(
            desc('call_count')
        ).limit(10).all()

        # 组装统计信息
        response["statistics"] = {
            "summary": {
                "total_calls": summary.total_calls or 0,
                "unique_users": summary.unique_users or 0,
                "unique_ips": summary.unique_ips or 0,
                "unique_paths": summary.unique_paths or 0,
                "total_duration": float(summary.total_duration or 0),
                "total_upload": int(summary.total_upload or 0),
                "total_download": int(summary.total_download or 0)
            },
            "user_stats": [
                {
                    "user": stat.username,
                    "call_count": stat.call_count,
                    "total_duration": float(stat.total_duration or 0),
                    "total_upload": int(stat.total_upload or 0),
                    "total_download": int(stat.total_download or 0)
                }
                for stat in user_stats
            ],
            "ip_stats": [
                {
                    "ip": stat.ip,
                    "call_count": stat.call_count,
                    "total_duration": float(stat.total_duration or 0),
                    "total_upload": int(stat.total_upload or 0),
                    "total_download": int(stat.total_download or 0)
                }
                for stat in ip_stats
            ],
            "path_stats": [
                {
                    "path": stat.path,
                    "call_count": stat.call_count,
                    "total_duration": float(stat.total_duration or 0),
                    "total_upload": int(stat.total_upload or 0),
                    "total_download": int(stat.total_download or 0)
                }
                for stat in path_stats
            ]
        }

    return response


# 提取设备信息（操作系统和浏览器）
def extract_device_info(user_agent: str):
    os = "Unknown OS"
    browser = "Unknown Browser"

    if "iPhone" in user_agent or "iPad" in user_agent:
        os = "iOS"
        browser = "Safari"
    elif "Android" in user_agent:
        os = "Android"
        browser = "Chrome"
    elif "Windows" in user_agent:
        os = "Windows"
        browser = "Chrome"
    elif "Macintosh" in user_agent:
        os = "Mac OS"
        browser = "Safari"
    elif "Linux" in user_agent:
        os = "Linux"
        browser = "Firefox"

    if "Chrome" in user_agent:
        browser = "Chrome"
    elif "Firefox" in user_agent:
        browser = "Firefox"
    elif "Safari" in user_agent:
        browser = "Safari"
    elif "Edge" in user_agent:
        browser = "Edge"

    return os, browser