"""
会话统计业务逻辑

职责：
- 会话统计仪表板
- 在线用户统计
- 会话分析

注意：此模块不依赖FastAPI，可在任何地方调用
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func
from datetime import datetime, timedelta

from app.auth.models import Session


def get_session_stats(
    db: DBSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    会话统计仪表板

    Args:
        db: 数据库会话
        start_date: 统计开始时间
        end_date: 统计结束时间

    Returns:
        统计数据字典
    """
    query = db.query(Session)

    # 应用时间范围筛选
    if start_date:
        query = query.filter(Session.created_at >= start_date)
    if end_date:
        query = query.filter(Session.created_at <= end_date)

    now = datetime.utcnow()

    # 基础统计
    total_sessions = query.count()
    active_sessions = query.filter(
        Session.revoked == False,
        Session.expires_at > now
    ).count()
    revoked_sessions = query.filter(Session.revoked == True).count()
    expired_sessions = query.filter(
        Session.expires_at < now,
        Session.revoked == False
    ).count()
    suspicious_sessions = query.filter(Session.is_suspicious == True).count()

    # 唯一用户数
    unique_users = db.query(func.count(func.distinct(Session.user_id))).filter(
        Session.created_at >= start_date if start_date else True,
        Session.created_at <= end_date if end_date else True
    ).scalar() or 0

    # 在线时长统计
    total_seconds = db.query(func.sum(Session.total_online_seconds)).filter(
        Session.created_at >= start_date if start_date else True,
        Session.created_at <= end_date if end_date else True
    ).scalar() or 0
    total_hours = round(total_seconds / 3600, 2)

    avg_seconds = db.query(func.avg(Session.total_online_seconds)).filter(
        Session.created_at >= start_date if start_date else True,
        Session.created_at <= end_date if end_date else True
    ).scalar() or 0
    avg_hours = round(avg_seconds / 3600, 2)

    # Top 10 IP 变更最多的会话
    top_ip_query = db.query(
        Session.session_id,
        Session.username,
        Session.ip_change_count
    )
    if start_date:
        top_ip_query = top_ip_query.filter(Session.created_at >= start_date)
    if end_date:
        top_ip_query = top_ip_query.filter(Session.created_at <= end_date)

    top_ip = top_ip_query.order_by(Session.ip_change_count.desc()).limit(10).all()

    # Top 10 设备变更最多的会话
    top_device_query = db.query(
        Session.session_id,
        Session.username,
        Session.device_change_count
    )
    if start_date:
        top_device_query = top_device_query.filter(Session.created_at >= start_date)
    if end_date:
        top_device_query = top_device_query.filter(Session.created_at <= end_date)

    top_device = top_device_query.order_by(Session.device_change_count.desc()).limit(10).all()

    return {
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "revoked_sessions": revoked_sessions,
        "expired_sessions": expired_sessions,
        "suspicious_sessions": suspicious_sessions,
        "unique_users_with_sessions": unique_users,
        "total_online_hours": total_hours,
        "avg_session_duration_hours": avg_hours,
        "top_ip_changes": [
            {"session_id": s[0], "username": s[1], "count": s[2]}
            for s in top_ip
        ],
        "top_device_changes": [
            {"session_id": s[0], "username": s[1], "count": s[2]}
            for s in top_device
        ]
    }


def get_online_users(
    db: DBSession,
    threshold_minutes: int = 5
) -> Dict[str, Any]:
    """
    获取在线用户列表

    Args:
        db: 数据库会话
        threshold_minutes: 在线阈值（分钟）

    Returns:
        在线用户数据字典
    """
    threshold = datetime.utcnow() - timedelta(minutes=threshold_minutes)

    # 查询最近活跃的会话
    online_sessions = db.query(Session).filter(
        Session.revoked == False,
        Session.last_activity_at >= threshold
    ).all()

    # 按用户分组
    users_dict = {}
    for session in online_sessions:
        if session.user_id not in users_dict:
            users_dict[session.user_id] = {
                "user_id": session.user_id,
                "username": session.username,
                "session_count": 0,
                "last_activity": session.last_activity_at,
                "sessions": []
            }

        users_dict[session.user_id]["session_count"] += 1
        users_dict[session.user_id]["sessions"].append({
            "session_id": session.session_id,
            "device_info": session.device_info,
            "current_ip": session.current_ip,
            "last_activity_at": session.last_activity_at
        })

        # 更新最后活动时间
        if session.last_activity_at > users_dict[session.user_id]["last_activity"]:
            users_dict[session.user_id]["last_activity"] = session.last_activity_at

    users = list(users_dict.values())
    users.sort(key=lambda u: u["last_activity"], reverse=True)

    return {
        "threshold_minutes": threshold_minutes,
        "online_user_count": len(users),
        "total_online_sessions": len(online_sessions),
        "users": users
    }


def get_user_session_history(
    db: DBSession,
    user_id: int,
    skip: int = 0,
    limit: int = 50
) -> Optional[Dict[str, Any]]:
    """
    获取用户的会话历史

    Args:
        db: 数据库会话
        user_id: 用户ID
        skip: 分页偏移
        limit: 分页限制

    Returns:
        会话历史字典，如果用户不存在则返回None
    """
    from app.auth.models import User
    from app.admin.sessions.core import build_session_summary

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    # 查询用户的所有会话
    query = db.query(Session).filter(Session.user_id == user_id)
    total = query.count()

    sessions = query.order_by(Session.created_at.desc()).offset(skip).limit(limit).all()

    # 统计
    active_count = db.query(Session).filter(
        Session.user_id == user_id,
        Session.revoked == False,
        Session.expires_at > datetime.utcnow()
    ).count()

    return {
        "user_id": user_id,
        "username": user.username,
        "total": total,
        "active_count": active_count,
        "skip": skip,
        "limit": limit,
        "sessions": [build_session_summary(db, s) for s in sessions]
    }


def get_analytics(
    db: DBSession,
    days: int = 30
) -> Dict[str, Any]:
    """
    会话分析（时间序列、地理分布、设备分布）

    Args:
        db: 数据库会话
        days: 分析天数

    Returns:
        分析数据字典
    """
    from app.admin.analytics.geo import lookup_ip_location

    start_date = datetime.utcnow() - timedelta(days=days)

    # 时间序列：每日新建会话数
    daily_sessions = db.query(
        func.date(Session.created_at).label('date'),
        func.count(Session.id).label('count')
    ).filter(
        Session.created_at >= start_date
    ).group_by(
        func.date(Session.created_at)
    ).order_by('date').all()

    # 地理分布：按国家/地区统计
    sessions_with_ip = db.query(Session).filter(
        Session.created_at >= start_date,
        Session.current_ip.isnot(None)
    ).all()

    country_stats = {}
    city_stats = {}

    for session in sessions_with_ip:
        location = lookup_ip_location(session.current_ip)
        if location:
            country = location.get("country", "Unknown")
            city = location.get("city", "Unknown")

            country_stats[country] = country_stats.get(country, 0) + 1
            city_key = f"{city}, {country}"
            city_stats[city_key] = city_stats.get(city_key, 0) + 1

    # 转换为列表并排序
    country_distribution = [
        {"country": k, "count": v}
        for k, v in sorted(country_stats.items(), key=lambda x: x[1], reverse=True)
    ][:20]  # Top 20

    city_distribution = [
        {"city": k, "count": v}
        for k, v in sorted(city_stats.items(), key=lambda x: x[1], reverse=True)
    ][:20]  # Top 20

    # 设备分布：从 device_info 提取
    device_stats = {}
    for session in db.query(Session).filter(Session.created_at >= start_date).all():
        if session.device_info:
            # 简单提取操作系统
            device_info = session.device_info.lower()
            if "windows" in device_info:
                os = "Windows"
            elif "mac" in device_info or "darwin" in device_info:
                os = "macOS"
            elif "linux" in device_info:
                os = "Linux"
            elif "android" in device_info:
                os = "Android"
            elif "ios" in device_info or "iphone" in device_info or "ipad" in device_info:
                os = "iOS"
            else:
                os = "Other"

            device_stats[os] = device_stats.get(os, 0) + 1

    device_distribution = [
        {"device": k, "count": v}
        for k, v in sorted(device_stats.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "period_days": days,
        "start_date": start_date.isoformat(),
        "daily_sessions": [
            {"date": str(d[0]), "count": d[1]}
            for d in daily_sessions
        ],
        "country_distribution": country_distribution,
        "city_distribution": city_distribution,
        "device_distribution": device_distribution
    }
