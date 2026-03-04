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
    from app.auth.models import ApiUsageLog
    from collections import defaultdict

    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # 查询时间范围内的所有会话
    sessions = db.query(Session).filter(
        Session.created_at >= start_date
    ).all()

    # 1. 登录热力图（7x24）
    login_heatmap = [[0 for _ in range(24)] for _ in range(7)]
    for session in sessions:
        weekday = session.created_at.weekday()  # 0=周一, 6=周日
        # 转换为 0=周日, 1=周一, ..., 6=周六
        weekday = (weekday + 1) % 7
        hour = session.created_at.hour
        login_heatmap[weekday][hour] += 1

    # 2. DAU/WAU/MAU 计算
    # DAU & WAU: 使用 ApiUsageLog（准确反映 API 使用情况，保留7天）
    # MAU: 使用 Session.created_at（ApiUsageLog 只保留7天，无法计算30天数据）

    # DAU: 每日活跃用户数（基于 API 调用）
    dau_dict = defaultdict(set)

    # 查询最近30天的 API 调用记录（实际只有7天数据）
    api_logs = db.query(ApiUsageLog).filter(
        ApiUsageLog.user_id.isnot(None),
        ApiUsageLog.called_at >= start_date
    ).all()

    for log in api_logs:
        date_str = log.called_at.date().isoformat()
        dau_dict[date_str].add(log.user_id)

    dau_list = [
        {"date": date, "count": len(users)}
        for date, users in sorted(dau_dict.items())
    ]

    # WAU: 最近7天有 API 调用的唯一用户数
    wau_start_date = now - timedelta(days=7)
    wau_users = db.query(ApiUsageLog.user_id).filter(
        ApiUsageLog.user_id.isnot(None),
        ApiUsageLog.called_at >= wau_start_date
    ).distinct().all()
    wau = len(wau_users)

    # MAU: 最近30天登录过的唯一用户数（基于 Session.created_at）
    mau_users = set()
    for session in sessions:
        mau_users.add(session.user_id)
    mau = len(mau_users)

    # 3. 设备类型分布
    device_counts = {
        "desktop": 0,
        "mobile": 0,
        "tablet": 0,
        "unknown": 0
    }

    for session in sessions:
        if not session.device_info:
            device_counts["unknown"] += 1
            continue

        device_lower = session.device_info.lower()
        if any(keyword in device_lower for keyword in ["mobile", "android", "iphone", "ipad"]):
            if "ipad" in device_lower or "tablet" in device_lower:
                device_counts["tablet"] += 1
            else:
                device_counts["mobile"] += 1
        else:
            device_counts["desktop"] += 1

    # 4. 地理分布：按国家/地区统计
    country_stats = {}

    for session in sessions:
        if session.current_ip:
            location = lookup_ip_location(session.current_ip)
            if location:
                # location 是字符串格式 "国家 - 城市" 或 "国家"
                parts = location.split(" - ", 1)
                country = parts[0] if parts else "Unknown"
                country_stats[country] = country_stats.get(country, 0) + 1

    # 转换为列表并排序
    geo_distribution = [
        {"country": k, "count": v}
        for k, v in sorted(country_stats.items(), key=lambda x: x[1], reverse=True)
    ][:20]  # Top 20

    # 5. 会话时长分布
    duration_counts = {
        "0-5min": 0,
        "5-30min": 0,
        "30-60min": 0,
        "1-2h": 0,
        "2h+": 0
    }

    for session in sessions:
        minutes = session.total_online_seconds / 60
        if minutes < 5:
            duration_counts["0-5min"] += 1
        elif minutes < 30:
            duration_counts["5-30min"] += 1
        elif minutes < 60:
            duration_counts["30-60min"] += 1
        elif minutes < 120:
            duration_counts["1-2h"] += 1
        else:
            duration_counts["2h+"] += 1

    # 构建响应
    return {
        "login_heatmap": login_heatmap,
        "user_activity": {
            "dau": dau_list,
            "wau": wau,
            "mau": mau
        },
        "device_distribution": device_counts,
        "geo_distribution": geo_distribution,
        "session_duration_distribution": duration_counts
    }
