"""
会话管理核心业务逻辑

职责：
- 解析IP历史
- 计算活跃token数
- 构建会话详情和摘要
- 查询会话列表
- 获取会话详情
- 撤销会话

注意：此模块不依赖FastAPI，可在任何地方调用
"""
import json
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session as DBSession
from datetime import datetime

from app.service.auth.database.models import User, Session, RefreshToken
from app.service.admin.analytics.geo import lookup_ip_location
from app.schemas.auth.session import (
    SessionDetailResponse,
    SessionSummaryResponse,
    IPHistoryItem
)


def parse_ip_history(ip_history_json: Optional[str]) -> List[IPHistoryItem]:
    """
    解析 Session.ip_history JSON 字段

    Args:
        ip_history_json: IP历史JSON字符串

    Returns:
        IP历史项列表
    """
    if not ip_history_json:
        return []
    try:
        data = json.loads(ip_history_json)
        return [IPHistoryItem(**item) for item in data]
    except Exception:
        return []


def get_active_token_count(db: DBSession, session_id: int) -> int:
    """
    计算会话的活跃 token 数量

    Args:
        db: 数据库会话
        session_id: 会话ID

    Returns:
        活跃token数量
    """
    now = datetime.utcnow()
    return db.query(RefreshToken).filter(
        RefreshToken.session_id == session_id,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > now
    ).count()


def build_session_detail(db: DBSession, session: Session) -> SessionDetailResponse:
    """
    构建会话详情响应

    Args:
        db: 数据库会话
        session: Session对象

    Returns:
        会话详情响应对象
    """
    # 解析 IP 历史并动态添加地理位置
    ip_history_items = []
    for item in parse_ip_history(session.ip_history):
        ip_history_items.append(IPHistoryItem(
            ip=item.ip,
            location=lookup_ip_location(item.ip),
            timestamp=item.timestamp
        ))

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
        current_ip_location=lookup_ip_location(session.current_ip),
        first_ip=session.first_ip,
        first_ip_location=lookup_ip_location(session.first_ip),
        ip_change_count=session.ip_change_count,
        ip_history=ip_history_items,
        refresh_count=session.refresh_count,
        total_online_seconds=session.total_online_seconds,
        current_session_started_at=session.current_session_started_at,
        last_seen=session.last_seen,
        is_suspicious=session.is_suspicious,
        suspicious_reason=session.suspicious_reason,
        active_token_count=get_active_token_count(db, session.id)
    )


def build_session_summary(db: DBSession, session: Session) -> SessionSummaryResponse:
    """
    构建会话摘要响应

    Args:
        db: 数据库会话
        session: Session对象

    Returns:
        会话摘要响应对象
    """
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
        current_ip_location=lookup_ip_location(session.current_ip),
        device_info=session.device_info,
        is_suspicious=session.is_suspicious,
        refresh_count=session.refresh_count,
        active_token_count=get_active_token_count(db, session.id)
    )


def list_sessions(
    db: DBSession,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    is_suspicious: Optional[bool] = None,
    revoked: Optional[bool] = None,
    ip_address: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    skip: int = 0,
    limit: int = 100
) -> Dict[str, Any]:
    """
    列出会话（高级过滤）

    Args:
        db: 数据库会话
        user_id: 按用户ID筛选
        username: 按用户名筛选
        is_suspicious: 筛选可疑会话
        revoked: 筛选撤销状态
        ip_address: 按当前IP筛选
        created_after: 创建时间范围（起）
        created_before: 创建时间范围（止）
        sort_by: 排序字段
        sort_order: 排序方向
        skip: 分页偏移
        limit: 分页限制

    Returns:
        包含total和sessions的字典
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
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "sessions": [build_session_summary(db, s) for s in sessions]
    }


def get_session_detail(db: DBSession, session_id: int) -> Optional[SessionDetailResponse]:
    """
    获取会话详情

    Args:
        db: 数据库会话
        session_id: 会话ID

    Returns:
        会话详情响应对象，如果不存在则返回None
    """
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        return None
    return build_session_detail(db, session)


def revoke_session(
    db: DBSession,
    session_id: int,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    撤销会话

    Args:
        db: 数据库会话
        session_id: 会话ID
        reason: 撤销原因

    Returns:
        结果字典
    """
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        return {
            "success": False,
            "error": "Session not found"
        }

    if session.revoked:
        return {
            "success": False,
            "error": "Session already revoked"
        }

    # 撤销会话
    session.revoked = True
    session.revoked_at = datetime.utcnow()
    session.revoked_reason = reason or "Revoked by admin"

    # 撤销所有关联的 RefreshToken
    db.query(RefreshToken).filter(
        RefreshToken.session_id == session_id,
        RefreshToken.revoked == False
    ).update({"revoked": True})

    db.commit()
    db.refresh(session)

    return {
        "success": True,
        "session": build_session_detail(db, session)
    }


def revoke_sessions_bulk(
    db: DBSession,
    session_ids: List[int],
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    批量撤销会话

    Args:
        db: 数据库会话
        session_ids: 会话ID列表
        reason: 撤销原因

    Returns:
        结果字典
    """
    if not session_ids:
        return {
            "success": False,
            "error": "No session IDs provided"
        }

    # 查找所有会话
    sessions = db.query(Session).filter(Session.id.in_(session_ids)).all()
    if not sessions:
        return {
            "success": False,
            "error": "No sessions found"
        }

    revoked_count = 0
    already_revoked_count = 0
    failed_ids = []

    for session in sessions:
        if session.revoked:
            already_revoked_count += 1
            continue

        try:
            # 撤销会话
            session.revoked = True
            session.revoked_at = datetime.utcnow()
            session.revoked_reason = reason or "Bulk revoked by admin"

            # 撤销所有关联的 RefreshToken
            db.query(RefreshToken).filter(
                RefreshToken.session_id == session.id,
                RefreshToken.revoked == False
            ).update({"revoked": True}, synchronize_session=False)

            revoked_count += 1
        except Exception as e:
            failed_ids.append(session.id)

    db.commit()

    return {
        "success": True,
        "revoked_count": revoked_count,
        "already_revoked_count": already_revoked_count,
        "failed_count": len(failed_ids),
        "failed_ids": failed_ids
    }


def revoke_user_sessions(
    db: DBSession,
    user_id: int,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    撤销用户的所有会话

    Args:
        db: 数据库会话
        user_id: 用户ID
        reason: 撤销原因

    Returns:
        结果字典
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {
            "success": False,
            "error": "User not found"
        }

    # 查找所有活跃会话
    active_sessions = db.query(Session).filter(
        Session.user_id == user_id,
        Session.revoked == False
    ).all()

    if not active_sessions:
        return {
            "success": True,
            "message": f"No active sessions for user {user.username}",
            "revoked_count": 0
        }

    # 撤销所有会话
    for session in active_sessions:
        session.revoked = True
        session.revoked_at = datetime.utcnow()
        session.revoked_reason = reason or f"All sessions revoked by admin"

    # 撤销所有关联的 RefreshToken
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False
    ).update({"revoked": True})

    db.commit()

    return {
        "success": True,
        "message": f"All sessions revoked for user {user.username}",
        "user_id": user_id,
        "username": user.username,
        "revoked_count": len(active_sessions)
    }


def flag_session(
    db: DBSession,
    session_id: int,
    is_suspicious: bool,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    标记会话为可疑/正常

    Args:
        db: 数据库会话
        session_id: 会话ID
        is_suspicious: 是否可疑
        reason: 标记原因

    Returns:
        结果字典
    """
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        return {
            "success": False,
            "error": "Session not found"
        }

    session.is_suspicious = is_suspicious
    session.suspicious_reason = reason if is_suspicious else None

    db.commit()
    db.refresh(session)

    return {
        "success": True,
        "session": build_session_detail(db, session)
    }
