"""
API使用统计业务逻辑层

职责：
- API使用日志查询
- 用户API使用统计
- IP统计
- 路径统计
- 设备信息提取

注意：此模块不依赖FastAPI，可在任何地方调用
"""
from typing import List, Dict, Any, Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc
from app.auth import models
from app.admin.analytics.geo import lookup_ip_location


def extract_device_info(user_agent: str) -> tuple:
    """
    提取设备信息（操作系统和浏览器）

    Args:
        user_agent: User-Agent字符串

    Returns:
        (os, browser) 元组
    """
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


def get_api_usage_summary(db: Session, query: str) -> Optional[List]:
    """
    获取用户的API使用摘要

    Args:
        db: 数据库会话
        query: 用户名或邮箱

    Returns:
        API使用摘要列表，如果用户不存在则返回None
    """
    if not query:
        return None

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        return None

    # 返回该用户的 API 使用统计
    return db.query(models.ApiUsageSummary).filter(
        models.ApiUsageSummary.user_id == user.id
    ).all()


def get_user_api_detail(db: Session, query: str) -> Optional[Dict[str, Any]]:
    """
    获取用户的API使用详情

    Args:
        db: 数据库会话
        query: 用户名

    Returns:
        API使用详情字典，如果用户不存在则返回None
    """
    if not query:
        return None

    # 查找用户，支持通过 username 查找
    user = db.query(models.User).filter(
        models.User.username == query
    ).first()

    if not user:
        return None

    api_logs = db.query(models.ApiUsageLog).filter(
        models.ApiUsageLog.user_id == user.id,
        models.ApiUsageLog.path != '/login'
    ).all()

    api_logs.sort(key=lambda log: log.called_at, reverse=True)

    # 返回 API 使用记录
    return {"user": user.username, "api_logs": api_logs}


def get_all_api_usage(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    sort_by: Optional[Literal["user", "ip", "path", "duration", "os", "browser", "called_at", "request_size", "response_size"]] = None,
    sort_order: Optional[Literal["asc", "desc"]] = "desc",
    include_stats: bool = False
) -> Dict[str, Any]:
    """
    获取所有API使用日志（增强版）

    Args:
        db: 数据库会话
        skip: 分页偏移
        limit: 分页限制
        search: 搜索关键词（匹配 user/ip/path/user_agent）
        sort_by: 排序字段
        sort_order: 排序方向
        include_stats: 是否返回全局统计信息

    Returns:
        包含日志和统计信息的字典
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
        stats = _get_api_usage_stats(db, search)
        response["statistics"] = stats

    return response


def _get_api_usage_stats(db: Session, search: Optional[str] = None) -> Dict[str, Any]:
    """
    获取API使用统计信息（内部函数）

    Args:
        db: 数据库会话
        search: 搜索关键词

    Returns:
        统计信息字典
    """
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

    # 用户统计
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
    ).all()

    # IP 统计
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
    ).all()

    # 路径统计
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
    ).all()

    # 组装统计信息
    return {
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
                "location": lookup_ip_location(stat.ip) if stat.ip else None,
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
