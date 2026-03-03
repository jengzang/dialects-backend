"""
基于 Session 模型的会话管理 API
提供完整的会话追踪、统计和管理功能
推荐使用此 API 替代 /admin/sessions/* (基于 RefreshToken)
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func, and_, or_
from typing import Optional, List
from datetime import datetime

from app.auth.dependencies import get_current_admin_user
from app.auth.models import User, Session, RefreshToken
from app.auth.database import get_db
from app.auth import session_service
from app.schemas.session import (
    SessionDetailResponse,
    SessionSummaryResponse,
    SessionListResponse,
    SessionStatsResponse,
    SessionActivityItem,
    SessionActivityResponse,
    RevokeSessionRequest,
    RevokeSessionResponse,
    RevokeBulkResponse,
    FlagSessionRequest,
    IPHistoryItem,
    AnalyticsResponse,
    OnlineUsersResponse
)

router = APIRouter()


def parse_ip_history(ip_history_json: Optional[str]) -> List[IPHistoryItem]:
    """解析 Session.ip_history JSON 字段"""
    if not ip_history_json:
        return []
    try:
        data = json.loads(ip_history_json)
        return [IPHistoryItem(**item) for item in data]
    except Exception:
        return []


def get_active_token_count(db: DBSession, session_id: int) -> int:
    """计算会话的活跃 token 数量"""
    now = datetime.utcnow()
    return db.query(RefreshToken).filter(
        RefreshToken.session_id == session_id,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > now
    ).count()


def build_session_detail(db: DBSession, session: Session) -> SessionDetailResponse:
    """构建会话详情响应"""
    return SessionDetailResponse(
        id=session.id,
        session_id=session.session_id,
        user_id=session.user_id,
        username=session.username,
        created_at=session.created_at,
        expires_at=session.expires_at,
        last_activity_at=session.last_activity_at,
        revoked=session.revoked,
        revoked_at=session.revoked_at,
        revoked_reason=session.revoked_reason,
        device_info=session.device_info,
        first_device_info=session.first_device_info,
        device_fingerprint=session.device_fingerprint,
        device_change_count=session.device_change_count,
        device_changed=session.device_changed,
        current_ip=session.current_ip,
        first_ip=session.first_ip,
        ip_change_count=session.ip_change_count,
        ip_history=parse_ip_history(session.ip_history),
        refresh_count=session.refresh_count,
        total_online_seconds=session.total_online_seconds,
        current_session_started_at=session.current_session_started_at,
        last_seen=session.last_seen,
        is_suspicious=session.is_suspicious,
        suspicious_reason=session.suspicious_reason,
        active_token_count=get_active_token_count(db, session.id)
    )


def build_session_summary(db: DBSession, session: Session) -> SessionSummaryResponse:
    """构建会话摘要响应"""
    return SessionSummaryResponse(
        id=session.id,
        session_id=session.session_id,
        user_id=session.user_id,
        username=session.username,
        created_at=session.created_at,
        expires_at=session.expires_at,
        last_activity_at=session.last_activity_at,
        revoked=session.revoked,
        current_ip=session.current_ip,
        device_info=session.device_info,
        is_suspicious=session.is_suspicious,
        refresh_count=session.refresh_count,
        active_token_count=get_active_token_count(db, session.id)
    )


@router.get("/list", response_model=SessionListResponse)
def list_sessions(
    user_id: Optional[int] = Query(None, description="按用户 ID 筛选"),
    username: Optional[str] = Query(None, description="按用户名筛选"),
    is_suspicious: Optional[bool] = Query(None, description="筛选可疑会话"),
    revoked: Optional[bool] = Query(None, description="筛选撤销状态"),
    ip_address: Optional[str] = Query(None, description="按当前 IP 筛选"),
    created_after: Optional[datetime] = Query(None, description="创建时间范围（起）"),
    created_before: Optional[datetime] = Query(None, description="创建时间范围（止）"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 (asc/desc)"),
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=500, description="分页限制"),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    列出会话（高级过滤）

    支持多字段组合过滤、排序和分页
    """
    query = db.query(Session)

    # 应用筛选条件
    if user_id is not None:
        query = query.filter(Session.user_id == user_id)

    if username is not None:
        query = query.filter(Session.username.like(f"%{username}%"))

    if is_suspicious is not None:
        query = query.filter(Session.is_suspicious == is_suspicious)

    if revoked is not None:
        query = query.filter(Session.revoked == revoked)

    if ip_address is not None:
        query = query.filter(Session.current_ip == ip_address)

    if created_after is not None:
        query = query.filter(Session.created_at >= created_after)

    if created_before is not None:
        query = query.filter(Session.created_at <= created_before)

    # 统计总数
    total = query.count()

    # 应用排序
    valid_sort_fields = [
        "created_at", "expires_at", "last_activity_at",
        "user_id", "username", "refresh_count", "ip_change_count", "device_change_count"
    ]
    if sort_by not in valid_sort_fields:
        sort_by = "created_at"

    sort_column = getattr(Session, sort_by)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # 分页
    sessions = query.offset(skip).limit(limit).all()

    # 构建响应
    return SessionListResponse(
        total=total,
        skip=skip,
        limit=limit,
        sessions=[build_session_summary(db, s) for s in sessions]
    )


@router.get("/stats", response_model=SessionStatsResponse)
def get_session_stats(
    start_date: Optional[datetime] = Query(None, description="统计开始时间"),
    end_date: Optional[datetime] = Query(None, description="统计结束时间"),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    会话统计仪表板

    提供全面的会话统计数据，包括总数、活跃数、可疑数、在线时长等
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

    return SessionStatsResponse(
        total_sessions=total_sessions,
        active_sessions=active_sessions,
        revoked_sessions=revoked_sessions,
        expired_sessions=expired_sessions,
        suspicious_sessions=suspicious_sessions,
        unique_users_with_sessions=unique_users,
        total_online_hours=total_hours,
        avg_session_duration_hours=avg_hours,
        top_ip_changes=[
            {"session_id": s[0], "username": s[1], "count": s[2]}
            for s in top_ip
        ],
        top_device_changes=[
            {"session_id": s[0], "username": s[1], "count": s[2]}
            for s in top_device
        ]
    )


@router.post("/revoke-bulk", response_model=RevokeBulkResponse)
def revoke_sessions_bulk(
    request: RevokeSessionRequest,
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    批量撤销会话

    批量撤销多个会话及其所有关联的 refresh token
    """
    revoked_count = 0
    failed_count = 0
    details = []

    for session_id in request.session_ids:
        try:
            session = db.query(Session).filter(Session.id == session_id).first()

            if not session:
                failed_count += 1
                details.append({
                    "session_id": session_id,
                    "status": "failed",
                    "reason": "Session not found"
                })
                continue

            if session.revoked:
                details.append({
                    "session_id": session_id,
                    "status": "skipped",
                    "reason": "Already revoked"
                })
                continue

            # 撤销会话
            session_service.revoke_session(db, session_id, request.reason)
            revoked_count += 1
            details.append({
                "session_id": session_id,
                "status": "success",
                "username": session.username
            })

        except Exception as e:
            failed_count += 1
            details.append({
                "session_id": session_id,
                "status": "error",
                "reason": str(e)
            })

    return RevokeBulkResponse(
        revoked_count=revoked_count,
        failed_count=failed_count,
        details=details
    )


@router.post("/revoke-user/{user_id}")
def revoke_user_sessions(
    user_id: int,
    reason: str = Query("admin_action", max_length=100),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    撤销用户所有会话

    撤销指定用户的所有活跃会话
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 查询所有活跃会话
    active_sessions = db.query(Session).filter(
        Session.user_id == user_id,
        Session.revoked == False
    ).all()

    revoked_count = 0
    for session in active_sessions:
        session_service.revoke_session(db, session.id, reason)
        revoked_count += 1

    return {
        "message": f"All sessions revoked for user {user.username}",
        "user_id": user_id,
        "username": user.username,
        "revoked_count": revoked_count
    }


@router.get("/user/{user_id}/history", response_model=SessionListResponse)
def get_user_session_history(
    user_id: int,
    include_revoked: bool = Query(True, description="是否包含已撤销的会话"),
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(50, ge=1, le=200, description="分页限制"),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    获取用户会话历史

    返回指定用户的所有会话，按创建时间降序排序
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = db.query(Session).filter(Session.user_id == user_id)

    if not include_revoked:
        query = query.filter(Session.revoked == False)

    total = query.count()
    sessions = query.order_by(Session.created_at.desc()).offset(skip).limit(limit).all()

    return SessionListResponse(
        total=total,
        skip=skip,
        limit=limit,
        sessions=[build_session_summary(db, s) for s in sessions]
    )


# ⚠️ IMPORTANT: Put wildcard routes AFTER all specific routes
# This ensures /stats, /list, etc. are matched before /{session_id}

@router.get("/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(
    session_id: int,
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    获取会话详情

    返回完整的会话信息，包括所有元数据和统计数据
    """
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return build_session_detail(db, session)


@router.get("/{session_id}/activity", response_model=SessionActivityResponse)
def get_session_activity(
    session_id: int,
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    获取会话活动时间线

    重建会话的完整活动历史，包括创建、刷新、IP/设备变更、标记、撤销等事件
    """
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    events: List[SessionActivityItem] = []

    # 1. 会话创建事件
    events.append(SessionActivityItem(
        timestamp=session.created_at,
        event_type="created",
        details=f"Session created from {session.first_ip}"
    ))

    # 2. Token 刷新事件
    tokens = db.query(RefreshToken).filter(
        RefreshToken.session_id == session.id
    ).order_by(RefreshToken.created_at).all()

    for token in tokens:
        events.append(SessionActivityItem(
            timestamp=token.created_at,
            event_type="refreshed",
            details=f"Token refreshed from {token.ip_address or 'unknown'}"
        ))

    # 3. IP 变更事件
    ip_history = parse_ip_history(session.ip_history)
    for i, ip_item in enumerate(ip_history):
        if i > 0:  # 跳过第一个 IP（已在创建事件中显示）
            try:
                timestamp = datetime.fromisoformat(ip_item.timestamp.replace('Z', '+00:00'))
                events.append(SessionActivityItem(
                    timestamp=timestamp,
                    event_type="ip_changed",
                    details=f"IP changed to {ip_item.ip}"
                ))
            except Exception:
                pass

    # 4. 设备变更事件
    if session.device_changed and session.device_change_count > 0:
        # 使用 last_activity_at 作为设备变更时间的近似值
        events.append(SessionActivityItem(
            timestamp=session.last_activity_at,
            event_type="device_changed",
            details=f"Device changed {session.device_change_count} time(s)"
        ))

    # 5. 可疑标记事件
    if session.is_suspicious:
        events.append(SessionActivityItem(
            timestamp=session.last_activity_at,
            event_type="flagged_suspicious",
            details=session.suspicious_reason or "Marked as suspicious"
        ))

    # 6. 撤销事件
    if session.revoked and session.revoked_at:
        events.append(SessionActivityItem(
            timestamp=session.revoked_at,
            event_type="revoked",
            details=f"Reason: {session.revoked_reason or 'unknown'}"
        ))

    # 按时间戳排序
    events.sort(key=lambda e: e.timestamp)

    return SessionActivityResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        username=session.username,
        events=events
    )


@router.post("/{session_id}/revoke", response_model=RevokeSessionResponse)
def revoke_session(
    session_id: int,
    reason: str = Query("admin_action", max_length=100),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    撤销单个会话

    撤销会话及其所有关联的 refresh token
    """
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.revoked:
        raise HTTPException(status_code=400, detail="Session already revoked")

    # 计算将要撤销的 token 数量
    token_count = db.query(RefreshToken).filter(
        RefreshToken.session_id == session_id,
        RefreshToken.revoked == False
    ).count()

    # 调用服务层撤销会话
    session_service.revoke_session(db, session_id, reason)

    return RevokeSessionResponse(
        message="Session revoked successfully",
        revoked_tokens=token_count
    )


@router.post("/{session_id}/flag", response_model=SessionDetailResponse)
def flag_session(
    session_id: int,
    request: FlagSessionRequest,
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    标记/取消标记可疑会话

    手动标记会话为可疑或正常
    """
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_suspicious = request.is_suspicious
    if request.is_suspicious and request.reason:
        session.suspicious_reason = request.reason
    elif not request.is_suspicious:
        session.suspicious_reason = None

    db.commit()
    db.refresh(session)

    return build_session_detail(db, session)


# ===== Analytics Endpoints =====

@router.get("/online-users", response_model=OnlineUsersResponse)
def get_online_users(
    threshold_minutes: int = Query(30, ge=1, le=120, description="在线判断阈值（分钟），默认30分钟"),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    获取实时在线用户列表

    判断标准：last_seen < threshold_minutes 分钟前

    说明：
    - last_seen 在 token 刷新时更新（约每 25-30 分钟）
    - 默认阈值 30 分钟，确保正常使用的用户都能被识别为在线
    - 可根据需要调整阈值（1-120 分钟）
    """
    from datetime import timedelta

    now = datetime.utcnow()
    threshold = now - timedelta(minutes=threshold_minutes)

    # 查询在线用户
    online_sessions = db.query(Session).filter(
        Session.revoked == False,
        Session.expires_at > now,
        Session.last_seen > threshold
    ).order_by(Session.last_seen.desc()).all()

    # 构建响应
    users = []
    for session in online_sessions:
        users.append({
            "user_id": session.user_id,
            "username": session.username,
            "last_seen": session.last_seen,
            "current_ip": session.current_ip,
            "device_info": session.device_info
        })

    return OnlineUsersResponse(
        online_count=len(users),
        users=users
    )


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    获取聚合统计数据

    包括：登录热力图、DAU/MAU、设备分布、地理分布、会话时长分布
    """
    from datetime import timedelta
    from collections import defaultdict
    import re

    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    # 查询时间范围内的所有会话
    sessions = db.query(Session).filter(
        Session.created_at >= start_date
    ).all()

    # 1. 登录热力图数据（7x24 二维数组）
    # 初始化：7天 x 24小时
    heatmap = [[0 for _ in range(24)] for _ in range(7)]

    for session in sessions:
        hour = session.created_at.hour
        weekday = session.created_at.weekday()  # 0=周一, 6=周日
        # 转换为 0=周日, 1=周一, ..., 6=周六
        weekday_adjusted = (weekday + 1) % 7

        heatmap[weekday_adjusted][hour] += 1

    # 2. DAU 趋势（最近30天）
    dau_dict = defaultdict(set)
    for session in sessions:
        date_str = session.last_seen.date().isoformat() if session.last_seen else session.created_at.date().isoformat()
        dau_dict[date_str].add(session.user_id)

    dau_list = [
        {"date": date, "count": len(users)}
        for date, users in sorted(dau_dict.items())
    ]

    # MAU（最近30天活跃用户总数）
    all_active_users = set()
    for users in dau_dict.values():
        all_active_users.update(users)
    mau = len(all_active_users)

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

    # 4. IP 地理分布（简化版：只统计 IP 前缀）
    # 注意：真实的地理位置需要 GeoIP 数据库，这里只做简单统计
    ip_counts = defaultdict(int)
    for session in sessions:
        # 简化处理：提取 IP 的前两段作为"地区"
        ip = session.first_ip
        if ip:
            # 简单分类：内网 vs 外网
            if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
                ip_counts["LAN"] += 1
            else:
                # 提取前两段
                parts = ip.split(".")
                if len(parts) >= 2:
                    prefix = f"{parts[0]}.{parts[1]}.x.x"
                    ip_counts[prefix] += 1
                else:
                    ip_counts["Unknown"] += 1

    geo_distribution = [
        {"country": region, "count": count}
        for region, count in sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

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
    return AnalyticsResponse(
        login_heatmap=heatmap,
        user_activity={
            "dau": dau_list,
            "mau": mau
        },
        device_distribution=device_counts,
        geo_distribution=geo_distribution,
        session_duration_distribution=duration_counts
    )
