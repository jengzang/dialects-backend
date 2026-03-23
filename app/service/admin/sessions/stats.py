"""
浼氳瘽缁熻涓氬姟閫昏緫

鑱岃矗锛?
- 浼氳瘽缁熻浠〃鏉?
- 鍦ㄧ嚎鐢ㄦ埛缁熻
- 浼氳瘽鍒嗘瀽

娉ㄦ剰锛氭妯″潡涓嶄緷璧朏astAPI锛屽彲鍦ㄤ换浣曞湴鏂硅皟鐢?
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func
from datetime import datetime, timedelta

from app.common.time_utils import to_shanghai_datetime

from app.service.auth.database.models import Session


def get_session_stats(
    db: DBSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    浼氳瘽缁熻浠〃鏉?

    Args:
        db: 鏁版嵁搴撲細璇?
        start_date: 缁熻寮€濮嬫椂闂?
        end_date: 缁熻缁撴潫鏃堕棿

    Returns:
        缁熻鏁版嵁瀛楀吀
    """
    query = db.query(Session)

    # 搴旂敤鏃堕棿鑼冨洿绛涢€?
    if start_date:
        query = query.filter(Session.created_at >= start_date)
    if end_date:
        query = query.filter(Session.created_at <= end_date)

    now = datetime.utcnow()

    # 鍩虹缁熻
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

    # 鍞竴鐢ㄦ埛鏁?
    unique_users = db.query(func.count(func.distinct(Session.user_id))).filter(
        Session.created_at >= start_date if start_date else True,
        Session.created_at <= end_date if end_date else True
    ).scalar() or 0

    # 鍦ㄧ嚎鏃堕暱缁熻
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

    # Top 10 IP 鍙樻洿鏈€澶氱殑浼氳瘽
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

    # Top 10 璁惧鍙樻洿鏈€澶氱殑浼氳瘽
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
    鑾峰彇鍦ㄧ嚎鐢ㄦ埛鍒楄〃

    Args:
        db: 鏁版嵁搴撲細璇?
        threshold_minutes: 鍦ㄧ嚎闃堝€硷紙鍒嗛挓锛?

    Returns:
        鍦ㄧ嚎鐢ㄦ埛鏁版嵁瀛楀吀
    """
    threshold = datetime.utcnow() - timedelta(minutes=threshold_minutes)

    # 鏌ヨ鏈€杩戞椿璺冪殑浼氳瘽
    online_sessions = db.query(Session).filter(
        Session.revoked == False,
        Session.last_activity_at >= threshold
    ).all()

    # 鎸夌敤鎴峰垎缁?
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

        # 鏇存柊鏈€鍚庢椿鍔ㄦ椂闂?
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
    鑾峰彇鐢ㄦ埛鐨勪細璇濆巻鍙?

    Args:
        db: 鏁版嵁搴撲細璇?
        user_id: 鐢ㄦ埛ID
        skip: 鍒嗛〉鍋忕Щ
        limit: 鍒嗛〉闄愬埗

    Returns:
        浼氳瘽鍘嗗彶瀛楀吀锛屽鏋滅敤鎴蜂笉瀛樺湪鍒欒繑鍥濶one
    """
    from app.service.auth.database.models import User
    from app.service.admin.sessions.core import build_session_summary

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    # 鏌ヨ鐢ㄦ埛鐨勬墍鏈変細璇?
    query = db.query(Session).filter(Session.user_id == user_id)
    total = query.count()

    sessions = query.order_by(Session.created_at.desc()).offset(skip).limit(limit).all()

    # 缁熻
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
    浼氳瘽鍒嗘瀽锛堟椂闂村簭鍒椼€佸湴鐞嗗垎甯冦€佽澶囧垎甯冿級

    Args:
        db: 鏁版嵁搴撲細璇?
        days: 鍒嗘瀽澶╂暟

    Returns:
        鍒嗘瀽鏁版嵁瀛楀吀
    """
    from app.service.admin.analytics.geo import lookup_ip_location
    from app.service.auth.database.models import ApiUsageLog
    from collections import defaultdict

    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # 鏌ヨ鏃堕棿鑼冨洿鍐呯殑鎵€鏈変細璇?
    sessions = db.query(Session).filter(
        Session.created_at >= start_date
    ).all()

    # 1. 鐧诲綍鐑姏鍥撅紙7x24锛?
    login_heatmap = [[0 for _ in range(24)] for _ in range(7)]
    for session in sessions:
        session_created_at = to_shanghai_datetime(session.created_at)
        weekday = session_created_at.weekday()  # 0=鍛ㄤ竴, 6=鍛ㄦ棩
        # 杞崲涓?0=鍛ㄦ棩, 1=鍛ㄤ竴, ..., 6=鍛ㄥ叚
        weekday = (weekday + 1) % 7
        hour = session_created_at.hour
        login_heatmap[weekday][hour] += 1

    # 2. DAU/WAU/MAU 璁＄畻
    # DAU & WAU: 浣跨敤 ApiUsageLog锛堝噯纭弽鏄?API 浣跨敤鎯呭喌锛屼繚鐣?澶╋級
    # MAU: 浣跨敤 Session.created_at锛圓piUsageLog 鍙繚鐣?澶╋紝鏃犳硶璁＄畻30澶╂暟鎹級

    # DAU: 姣忔棩娲昏穬鐢ㄦ埛鏁帮紙鍩轰簬 API 璋冪敤锛?
    dau_dict = defaultdict(set)

    # 鏌ヨ鏈€杩?0澶╃殑 API 璋冪敤璁板綍锛堝疄闄呭彧鏈?澶╂暟鎹級
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

    # WAU: 鏈€杩?澶╂湁 API 璋冪敤鐨勫敮涓€鐢ㄦ埛鏁?
    wau_start_date = now - timedelta(days=7)
    wau_users = db.query(ApiUsageLog.user_id).filter(
        ApiUsageLog.user_id.isnot(None),
        ApiUsageLog.called_at >= wau_start_date
    ).distinct().all()
    wau = len(wau_users)

    # MAU: 鏈€杩?0澶╃櫥褰曡繃鐨勫敮涓€鐢ㄦ埛鏁帮紙鍩轰簬 Session.created_at锛?
    mau_users = set()
    for session in sessions:
        mau_users.add(session.user_id)
    mau = len(mau_users)

    # 3. 璁惧绫诲瀷鍒嗗竷
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

    # 4. 鍦扮悊鍒嗗竷锛氭寜鍥藉/鍦板尯缁熻
    country_stats = {}

    for session in sessions:
        if session.current_ip:
            location = lookup_ip_location(session.current_ip)
            if location:
                # location 鏄瓧绗︿覆鏍煎紡 "鍥藉 - 鍩庡競" 鎴?"鍥藉"
                parts = location.split(" - ", 1)
                country = parts[0] if parts else "Unknown"
                country_stats[country] = country_stats.get(country, 0) + 1

    # 杞崲涓哄垪琛ㄥ苟鎺掑簭
    geo_distribution = [
        {"country": k, "count": v}
        for k, v in sorted(country_stats.items(), key=lambda x: x[1], reverse=True)
    ][:20]  # Top 20

    # 5. 浼氳瘽鏃堕暱鍒嗗竷
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

    # 鏋勫缓鍝嶅簲
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




