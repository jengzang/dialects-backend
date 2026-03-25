"""Session管理服务"""
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy import and_, exists
from sqlalchemy.orm import Session as DBSession

from app.service.auth.database.models import User, Session, RefreshToken
from app.service.auth.core.utils import create_access_token, create_token_pair, create_refresh_token
from app.common.auth_config import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    MAX_TOKENS_PER_SESSION,
    MAX_SESSIONS_PER_USER,
    SUSPICIOUS_IP_CHANGES,
    SUSPICIOUS_DEVICE_CHANGES,
    IP_HISTORY_LIMIT
)

REFRESH_REUSE_GRACE_SECONDS = 30


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _session_expiry_from(now: Optional[datetime] = None) -> datetime:
    base = now or _now_utc_naive()
    return base + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


def _has_active_refresh_token(
    db: DBSession,
    session_id: int,
    now: Optional[datetime] = None,
) -> bool:
    current_time = now or _now_utc_naive()
    return db.query(RefreshToken.id).filter(
        RefreshToken.session_id == session_id,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > current_time
    ).first() is not None


def active_refresh_token_exists_clause(now: Optional[datetime] = None):
    current_time = now or _now_utc_naive()
    return exists().where(and_(
        RefreshToken.session_id == Session.id,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > current_time,
    ))


def _revoke_session_record(
    db: DBSession,
    session: Session,
    *,
    reason: str,
    revoked_at: Optional[datetime] = None,
) -> None:
    current_time = revoked_at or _now_utc_naive()
    session.revoked = True
    session.revoked_at = current_time
    session.revoked_reason = reason

    db.query(RefreshToken).filter(
        RefreshToken.session_id == session.id,
        RefreshToken.revoked == False
    ).update({"revoked": True}, synchronize_session=False)


def reconcile_user_sessions(
    db: DBSession,
    user_id: int,
    *,
    now: Optional[datetime] = None,
) -> int:
    """
    Revoke stale sessions that should no longer count as active.

    This repairs historical data where logout revoked refresh tokens but left the
    session itself active, which would otherwise keep occupying the per-user
    session quota until the daily cleanup job ran.
    """
    current_time = now or _now_utc_naive()
    sessions = db.query(Session).filter(
        Session.user_id == user_id,
        Session.revoked == False
    ).all()

    changed = 0
    for session in sessions:
        if session.expires_at <= current_time:
            _revoke_session_record(
                db,
                session,
                reason="expired",
                revoked_at=current_time,
            )
            changed += 1
            continue

        if not _has_active_refresh_token(db, session.id, current_time):
            _revoke_session_record(
                db,
                session,
                reason="token_inactive",
                revoked_at=current_time,
            )
            changed += 1

    return changed


def get_user_active_sessions(
    db: DBSession,
    user_id: int,
    *,
    now: Optional[datetime] = None,
) -> list[Session]:
    current_time = now or _now_utc_naive()
    return db.query(Session).filter(
        Session.user_id == user_id,
        Session.revoked == False,
        Session.expires_at > current_time,
        active_refresh_token_exists_clause(current_time),
    ).order_by(Session.last_activity_at.desc()).all()


def get_valid_session_by_public_id(
    db: DBSession,
    public_session_id: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[Session]:
    current_time = now or _now_utc_naive()
    session = db.query(Session).filter(
        Session.session_id == public_session_id,
    ).first()

    if not session:
        return None
    if session.revoked or session.expires_at <= current_time:
        return None

    return session


def issue_access_token_for_session(user: User, session: Session) -> str:
    return create_access_token(user.username, user.role, session.session_id)


def _matches_refresh_request(
    token: RefreshToken,
    ip_address: str,
    device_info: str,
) -> bool:
    if (
        token.ip_address and ip_address and
        token.ip_address not in ("0.0.0.0", "", None) and
        ip_address not in ("0.0.0.0", "", None) and
        token.ip_address != ip_address
    ):
        return False

    if (
        token.device_info and device_info and
        token.device_info != "Unknown" and
        device_info != "Unknown" and
        token.device_info != device_info
    ):
        return False

    return True


def resolve_refresh_token_for_exchange(
    db: DBSession,
    token: str,
    *,
    ip_address: str,
    device_info: str,
) -> Tuple[Optional[RefreshToken], bool]:
    """
    Resolve a refresh token for exchange.

    Returns `(refresh_token, reused)` where `reused=True` means the caller sent
    a recently rotated token and should receive the already-issued replacement
    token instead of rotating again. This makes refresh idempotent across
    duplicate requests and multi-tab races.
    """
    now = _now_utc_naive()
    token_obj = db.query(RefreshToken).filter(
        RefreshToken.token == token
    ).first()

    if not token_obj:
        return None, False

    if token_obj.revoked:
        if not token_obj.replaced_by:
            return None, False

        replacement = db.query(RefreshToken).filter(
            RefreshToken.token == token_obj.replaced_by
        ).first()

        if not replacement:
            return None, False

        age_seconds = (
            (now - replacement.created_at).total_seconds()
            if replacement.created_at else None
        )
        if (
            replacement.revoked or
            replacement.expires_at <= now or
            replacement.user_id != token_obj.user_id or
            replacement.session_id != token_obj.session_id or
            age_seconds is None or
            age_seconds > REFRESH_REUSE_GRACE_SECONDS or
            not _matches_refresh_request(replacement, ip_address, device_info)
        ):
            return None, False

        session = replacement.session
        if session and (session.revoked or session.expires_at <= now):
            return None, False

        return replacement, True

    if token_obj.expires_at <= now:
        return None, False

    session = token_obj.session
    if session and (session.revoked or session.expires_at <= now):
        return None, False

    return token_obj, False


def revoke_session_by_public_id(
    db: DBSession,
    public_session_id: str,
    *,
    reason: str = "logout",
) -> bool:
    session = db.query(Session).filter(
        Session.session_id == public_session_id
    ).first()
    if not session:
        return False

    _revoke_session_record(db, session, reason=reason)
    db.commit()
    return True


def revoke_user_sessions(
    db: DBSession,
    user_id: int,
    *,
    reason: str = "logout_all",
) -> int:
    sessions = db.query(Session).filter(
        Session.user_id == user_id,
        Session.revoked == False,
    ).all()

    if not sessions:
        return 0

    revoked_at = _now_utc_naive()
    for session in sessions:
        _revoke_session_record(
            db,
            session,
            reason=reason,
            revoked_at=revoked_at,
        )

    db.commit()
    return len(sessions)


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
    now = _now_utc_naive()
    session_id = str(uuid.uuid4())

    reconcile_user_sessions(db, user.id, now=now)
    active_sessions = get_user_active_sessions(db, user.id, now=now)
    if len(active_sessions) >= MAX_SESSIONS_PER_USER:
        least_active_session = active_sessions[-1]
        _revoke_session_record(
            db,
            least_active_session,
            reason="max_sessions_exceeded",
            revoked_at=now,
        )

    # Apply intelligent IP fallback (only when needed)
    best_ip = _get_best_ip_address(db, user, ip_address)

    # Build IP history with first valid IP
    ip_history_data = []
    if best_ip and best_ip != "0.0.0.0":
        ip_history_data.append({
            "ip": best_ip,
            "timestamp": now.isoformat()
        })

    # 创建session记录
    session = Session(
        session_id=session_id,
        user_id=user.id,
        username=user.username,
        created_at=now,
        expires_at=_session_expiry_from(now),
        first_ip=best_ip,
        current_ip=best_ip,
        device_info=device_info,
        first_device_info=device_info,  # ✅ 记录首次设备
        device_fingerprint=device_fingerprint,
        ip_history=json.dumps(ip_history_data),
        current_session_started_at=now,  # ✅ Initialize timestamp
        last_seen=now  # ✅ Initialize last_seen
    )
    db.add(session)
    db.flush()  # 获取session.id

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
    now = _now_utc_naive()
    session = old_refresh_token.session
    user = old_refresh_token.user

    reconcile_user_sessions(db, user.id, now=now)

    # ✅ 处理旧token（没有session）的情况
    if session is None:
        # Apply intelligent fallbacks for migrated sessions without session_id
        best_ip = _get_best_ip_address(db, user, ip_address)

        # 为旧token创建新session
        session = Session(
            session_id=f"migrated-{user.id}-{uuid.uuid4().hex[:8]}",
            user_id=user.id,
            username=user.username,
            created_at=now,
            expires_at=_session_expiry_from(now),
            first_ip=best_ip,
            current_ip=best_ip,
            device_info=device_info,
            first_device_info=device_info,
            ip_history=json.dumps([]),
            refresh_count=0,
            current_session_started_at=now,  # ✅ Initialize timestamp
            last_seen=now  # ✅ Initialize last_seen
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
                    "timestamp": now.isoformat(),
                    "event": "backfilled"
                }])

    # ✅ BACKFILL: Initialize timestamp fields for migrated sessions
    if not session.current_session_started_at:
        session.current_session_started_at = now
        print(f"[BACKFILL] Initialized current_session_started_at for session {session.id}")

    if not session.last_seen:
        session.last_seen = now
        print(f"[BACKFILL] Initialized last_seen for session {session.id}")

    # Apply fallback for new current_ip (if extraction failed)
    new_current_ip = _get_best_ip_address(db, user, ip_address)
    session.expires_at = _session_expiry_from(now)

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
            ip_history.append({"ip": new_current_ip, "timestamp": now.isoformat()})
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
        session.last_activity_at = now

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
        _revoke_session_record(db, session, reason=reason)
        db.commit()
