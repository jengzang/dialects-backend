"""
Session statistics aggregation helpers.

This module powers the admin session analytics endpoints.
It provides aggregate counters, online user snapshots,
user session history, and higher-level analytics views.
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func
from datetime import datetime, timedelta

from app.common.time_utils import to_shanghai_datetime
from app.service.auth.database.models import Session
from app.service.auth.session.service import active_refresh_token_exists_clause


def get_session_stats(
    db: DBSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Aggregate session statistics.

    Args:
        db: Database session.
        start_date: Inclusive lower bound for the query window.
        end_date: Inclusive upper bound for the query window.

    Returns:
        Aggregated session statistics payload.
    """
    query = db.query(Session)

    if start_date:
        query = query.filter(Session.created_at >= start_date)
    if end_date:
        query = query.filter(Session.created_at <= end_date)

    now = datetime.utcnow()

    # Count sessions by status.
    total_sessions = query.count()
    active_sessions = query.filter(
        Session.revoked == False,
        Session.expires_at > now,
        active_refresh_token_exists_clause(now),
    ).count()
    revoked_sessions = query.filter(Session.revoked == True).count()
    expired_sessions = query.filter(
        Session.expires_at < now,
        Session.revoked == False
    ).count()
    suspicious_sessions = query.filter(Session.is_suspicious == True).count()

    # Count unique users in range.
    unique_users = db.query(func.count(func.distinct(Session.user_id))).filter(
        Session.created_at >= start_date if start_date else True,
        Session.created_at <= end_date if end_date else True
    ).scalar() or 0

    # Summarize online duration in range.
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

    # Top 10 sessions by IP-change count.
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

    # Top 10 sessions by device-change count.
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
    Fetch users with sessions that are still considered online.

    Args:
        db: Database session.
        threshold_minutes: Idle threshold, in minutes, for online status.

    Returns:
        Online-user summary payload.
    """
    from app.service.admin.analytics.geo import lookup_ip_location

    current_time = datetime.utcnow()
    threshold = current_time - timedelta(minutes=threshold_minutes)

    online_sessions = db.query(Session).filter(
        Session.revoked == False,
        Session.expires_at > current_time,
        Session.last_activity_at >= threshold,
        active_refresh_token_exists_clause(current_time),
    ).all()

    # Group sessions by user.
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
            "ip_location": lookup_ip_location(session.current_ip) if session.current_ip else None,
            "last_activity_at": session.last_activity_at
        })

        # Keep the most recent activity time per user.
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
    Fetch paginated session history for one user.

    Args:
        db: Database session.
        user_id: Target user ID.
        skip: Pagination offset.
        limit: Pagination limit.

    Returns:
        User session history payload or None.
    """
    from app.service.auth.database.models import User
    from app.service.admin.sessions.core import build_session_summary

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    query = db.query(Session).filter(Session.user_id == user_id)
    total = query.count()

    sessions = query.order_by(Session.created_at.desc()).offset(skip).limit(limit).all()

    # Count active sessions for the user.
    current_time = datetime.utcnow()
    active_count = db.query(Session).filter(
        Session.user_id == user_id,
        Session.revoked == False,
        Session.expires_at > current_time,
        active_refresh_token_exists_clause(current_time),
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
    Build analytics for recent session activity.

    Args:
        db: Database session.
        days: Lookback window, in days.

    Returns:
        Session analytics payload.
    """
    from collections import defaultdict

    from app.service.admin.analytics.geo import lookup_ip_location
    from app.service.auth.database.models import ApiUsageLog

    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # Load sessions within the analysis window.
    sessions = db.query(Session).filter(
        Session.created_at >= start_date
    ).all()

    # 1. Login heatmap.
    login_heatmap = [[0 for _ in range(24)] for _ in range(7)]
    for session in sessions:
        session_created_at = to_shanghai_datetime(session.created_at)
        weekday = session_created_at.weekday()  # 0=Monday, 6=Sunday
        weekday = (weekday + 1) % 7  # Convert to Sunday-first index.
        hour = session_created_at.hour
        login_heatmap[weekday][hour] += 1

    # 2. DAU/WAU/MAU.
    # DAU and WAU come from API usage logs.
    # MAU is derived from sessions created in the selected window.
    dau_dict = defaultdict(set)

    api_logs = db.query(ApiUsageLog).filter(
        ApiUsageLog.user_id.isnot(None),
        ApiUsageLog.called_at >= start_date
    ).all()

    for log in api_logs:
        date_str = to_shanghai_datetime(log.called_at).date().isoformat()
        dau_dict[date_str].add(log.user_id)

    dau_list = [
        {"date": date, "count": len(users)}
        for date, users in sorted(dau_dict.items())
    ]

    wau_start_date = now - timedelta(days=7)
    wau_users = db.query(ApiUsageLog.user_id).filter(
        ApiUsageLog.user_id.isnot(None),
        ApiUsageLog.called_at >= wau_start_date
    ).distinct().all()
    wau = len(wau_users)

    mau_users = {session.user_id for session in sessions}
    mau = len(mau_users)

    # 3. Device breakdown.
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

    # 4. Geographic distribution by country/region.
    country_stats = {}
    for session in sessions:
        if session.current_ip:
            location = lookup_ip_location(session.current_ip)
            if location:
                parts = location.split(" - ", 1)
                country = parts[0] if parts else "Unknown"
                country_stats[country] = country_stats.get(country, 0) + 1

    geo_distribution = [
        {"country": country, "count": count}
        for country, count in sorted(country_stats.items(), key=lambda item: item[1], reverse=True)
    ][:20]

    # 5. Session duration buckets.
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
