"""
会话活动追踪业务逻辑

职责：
- 获取会话活动时间线
- 重建会话历史事件

注意：此模块不依赖FastAPI，可在任何地方调用
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session as DBSession
from datetime import datetime

from app.service.auth.database.models import Session, RefreshToken
from app.service.admin.analytics.geo import lookup_ip_location
from app.service.admin.sessions.core import parse_ip_history
from app.schemas.session import SessionActivityItem


def get_session_activity(
    db: DBSession,
    session_id: int
) -> Optional[Dict[str, Any]]:
    """
    获取会话活动时间线

    重建会话的完整活动历史，包括创建、刷新、IP/设备变更、标记、撤销等事件

    Args:
        db: 数据库会话
        session_id: 会话ID

    Returns:
        活动时间线字典，如果会话不存在则返回None
    """
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        return None

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
                location = lookup_ip_location(ip_item.ip)
                location_str = f" ({location})" if location else ""
                events.append(SessionActivityItem(
                    timestamp=timestamp,
                    event_type="ip_changed",
                    details=f"IP changed to {ip_item.ip}{location_str}"
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

    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "username": session.username,
        "events": events
    }
