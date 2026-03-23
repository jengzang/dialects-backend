"""Session管理服务"""
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from app.service.auth.database.models import User, Session, RefreshToken
from app.service.auth.core.utils import create_token_pair, create_refresh_token
from app.common.auth_config import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    MAX_TOKENS_PER_SESSION,
    MAX_SESSIONS_PER_USER,
    SUSPICIOUS_IP_CHANGES,
    SUSPICIOUS_DEVICE_CHANGES,
    IP_HISTORY_LIMIT
)


def _get_best_ip_address(
    db: DBSession,
    user: User,
    current_ip: str
) -> str:
    """
    Get best IP address using intelligent fallbacks.

    Args:
        db: Database session
        user: User object
        current_ip: IP from current request

    Returns:
        Best available IP address with fallbacks applied
    """
    # Clean current value
    clean_ip = (current_ip or "").strip()

    # If current IP is valid, use it
    if clean_ip and clean_ip not in ("0.0.0.0", "", "None"):
        return clean_ip

    # Fallback 1: Query user's most recent session with valid IP
    last_session = db.query(Session).filter(
        Session.user_id == user.id,
        Session.current_ip.notin_(["0.0.0.0", "", None])
    ).order_by(Session.last_activity_at.desc()).first()

    if last_session and last_session.current_ip:
        return last_session.current_ip

    # Fallback 2: Use user table data
    if user.last_login_ip and user.last_login_ip not in ("0.0.0.0", "", None):
        return user.last_login_ip
    if user.register_ip and user.register_ip not in ("0.0.0.0", "", None):
        return user.register_ip

    # Final fallback
    return "0.0.0.0"


def should_update_session(session: Session) -> bool:
    """
    Determine if session should be updated.
    Only update if enough time has passed since last update (5 minutes).

    This throttles session writes to reduce database load during frequent token refreshes.
    """
    if not session.last_activity_at:
        return True

    time_since_update = datetime.now(timezone.utc).replace(tzinfo=None) - session.last_activity_at
    return time_since_update.total_seconds() > 300  # 5 minutes


def create_session(
    db: DBSession,
    user: User,
    device_info: str,
    ip_address: str,
    device_fingerprint: Optional[str] = None
) -> Tuple[Session, str, str]:
    """
    创建新会话
    返回: (session, access_token, refresh_token)
    """
    session_id = str(uuid.uuid4())

    # Apply intelligent IP fallback (only when needed)
    best_ip = _get_best_ip_address(db, user, ip_address)

    # Build IP history with first valid IP
    ip_history_data = []
    if best_ip and best_ip != "0.0.0.0":
        ip_history_data.append({
            "ip": best_ip,
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        })

    # 创建session记录
    session = Session(
        session_id=session_id,
        user_id=user.id,
        username=user.username,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        first_ip=best_ip,
        current_ip=best_ip,
        device_info=device_info,
        first_device_info=device_info,  # ✅ 记录首次设备
        device_fingerprint=device_fingerprint,
        ip_history=json.dumps(ip_history_data),
        current_session_started_at=datetime.now(timezone.utc).replace(tzinfo=None),  # ✅ Initialize timestamp
        last_seen=datetime.now(timezone.utc).replace(tzinfo=None)  # ✅ Initialize last_seen
    )
    db.add(session)
    db.flush()  # 获取session.id

    # ✅ 限制每个用户的session数量（最多MAX_SESSIONS_PER_USER个）
    user_sessions = db.query(Session).filter(
        Session.user_id == user.id,
        Session.revoked == False
    ).order_by(Session.last_activity_at.desc()).all()

    if len(user_sessions) >= MAX_SESSIONS_PER_USER:
        # 撤销最不活跃的session
        least_active_session = user_sessions[-1]
        revoke_session(db, least_active_session.id, reason="max_sessions_exceeded")

    # 生成token
    token_pair = create_token_pair(user.username, user.role, session.session_id)  # ✅ 传入session_id
    access_token = token_pair["access_token"]
    refresh_token_str = create_refresh_token()

    # 存储refresh token（关联到session）
    refresh_token = RefreshToken(
        token=refresh_token_str,
        session_id=session.id,
        user_id=user.id,
        expires_at=session.expires_at,
        ip_address=best_ip,
        device_info=device_info
    )
    db.add(refresh_token)

    db.commit()
    db.refresh(session)

    return session, access_token, refresh_token_str


def refresh_session(
    db: DBSession,
    old_refresh_token: RefreshToken,
    ip_address: str,
    device_info: str
) -> Tuple[str, str]:
    """
    刷新token并更新session
    返回: (new_access_token, new_refresh_token)
    """
    session = old_refresh_token.session
    user = old_refresh_token.user

    # ✅ 处理旧token（没有session）的情况
    if session is None:
        # Apply intelligent fallbacks for migrated sessions without session_id
        best_ip = _get_best_ip_address(db, user, ip_address)

        # 为旧token创建新session
        session = Session(
            session_id=f"migrated-{user.id}-{uuid.uuid4().hex[:8]}",
            user_id=user.id,
            username=user.username,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            first_ip=best_ip,
            current_ip=best_ip,
            device_info=device_info,
            first_device_info=device_info,
            ip_history=json.dumps([]),
            refresh_count=0,
            current_session_started_at=datetime.now(timezone.utc).replace(tzinfo=None),  # ✅ Initialize timestamp
            last_seen=datetime.now(timezone.utc).replace(tzinfo=None)  # ✅ Initialize last_seen
        )
        db.add(session)
        db.flush()  # 获取session.id

        # 关联旧token到新session
        old_refresh_token.session_id = session.id
        db.commit()

    # ✅ BACKFILL: Use session's own current_ip to fix first_ip
    # This is simpler than querying other sessions!
    if session.first_ip in ("0.0.0.0", "", None):
        if session.current_ip and session.current_ip not in ("0.0.0.0", "", None):
            # Session already has a valid current_ip, use it to backfill first_ip
            session.first_ip = session.current_ip
            print(f"[BACKFILL] Updated first_ip for session {session.id}: {session.current_ip}")

            # Initialize IP history if empty
            if not session.ip_history or session.ip_history == "[]":
                session.ip_history = json.dumps([{
                    "ip": session.current_ip,
                    "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                    "event": "backfilled"
                }])

    # ✅ BACKFILL: Initialize timestamp fields for migrated sessions
    if not session.current_session_started_at:
        session.current_session_started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        print(f"[BACKFILL] Initialized current_session_started_at for session {session.id}")

    if not session.last_seen:
        session.last_seen = datetime.now(timezone.utc).replace(tzinfo=None)
        print(f"[BACKFILL] Initialized last_seen for session {session.id}")

    # Apply fallback for new current_ip (if extraction failed)
    new_current_ip = _get_best_ip_address(db, user, ip_address)

    # ✅ Check if IP or device changed
    ip_changed = (new_current_ip != session.current_ip)
    device_changed = (device_info != session.device_info)

    # ✅ Determine if session needs update (throttle to reduce writes)
    needs_update = (
        ip_changed or
        device_changed or
        should_update_session(session)
    )

    if needs_update:
        # Update session only when necessary
        if ip_changed:
            session.ip_change_count += 1
            session.current_ip = new_current_ip

            # 更新IP历史
            ip_history = json.loads(session.ip_history or "[]")
            ip_history.append({"ip": new_current_ip, "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()})
            session.ip_history = json.dumps(ip_history[-IP_HISTORY_LIMIT:])  # 保留最近N条

            # 检测可疑活动
            if session.ip_change_count > SUSPICIOUS_IP_CHANGES:
                session.is_suspicious = True
                session.suspicious_reason = f"Excessive IP changes: {session.ip_change_count}"

        if device_changed:
            session.device_change_count += 1
            session.device_info = device_info  # 更新为最新设备
            session.device_changed = True  # 标记设备已变化

            # 检测可疑活动
            if session.device_change_count > SUSPICIOUS_DEVICE_CHANGES:
                session.is_suspicious = True
                session.suspicious_reason = f"Excessive device changes: {session.device_change_count}"

        # Update timestamps and counters
        session.refresh_count += 1
        session.last_activity_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.last_seen = datetime.now(timezone.utc).replace(tzinfo=None)
        session.current_session_started_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # ✅ Update User table (kept as per user requirement)
        user.last_seen = datetime.now(timezone.utc).replace(tzinfo=None)
        user.current_session_started_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # 创建新token对
    token_pair = create_token_pair(user.username, user.role, session.session_id)  # ✅ 传入session_id
    new_access_token = token_pair["access_token"]
    new_refresh_token_str = create_refresh_token()

    # 撤销旧token
    old_refresh_token.revoked = True
    old_refresh_token.replaced_by = new_refresh_token_str

    # 创建新refresh token
    new_token = RefreshToken(
        token=new_refresh_token_str,
        session_id=session.id,
        user_id=user.id,
        expires_at=session.expires_at,
        ip_address=new_current_ip,
        device_info=device_info
    )
    db.add(new_token)

    # ✅ 限制每个session的token历史记录
    all_tokens = db.query(RefreshToken).filter(
        RefreshToken.session_id == session.id
    ).order_by(RefreshToken.created_at.desc()).all()

    if len(all_tokens) > MAX_TOKENS_PER_SESSION:
        for old_token in all_tokens[MAX_TOKENS_PER_SESSION:]:
            db.delete(old_token)

    db.commit()

    return new_access_token, new_refresh_token_str


def revoke_session(db: DBSession, session_id: int, reason: str = "manual"):
    """撤销session及其所有token"""
    session = db.query(Session).filter(Session.id == session_id).first()
    if session:
        session.revoked = True
        session.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.revoked_reason = reason

        # 撤销所有关联token
        db.query(RefreshToken).filter(
            RefreshToken.session_id == session_id,
            RefreshToken.revoked == False
        ).update({"revoked": True})

        db.commit()
