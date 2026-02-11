"""Session管理服务"""
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from app.auth.models import User, Session, RefreshToken
from app.auth.utils import create_token_pair, create_refresh_token
from app.auth.config import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    MAX_TOKENS_PER_SESSION,
    MAX_SESSIONS_PER_USER,
    SUSPICIOUS_IP_CHANGES,
    SUSPICIOUS_DEVICE_CHANGES,
    IP_HISTORY_LIMIT
)


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

    # 创建session记录
    session = Session(
        session_id=session_id,
        user_id=user.id,
        username=user.username,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        first_ip=ip_address,
        current_ip=ip_address,
        device_info=device_info,
        first_device_info=device_info,  # ✅ 记录首次设备
        device_fingerprint=device_fingerprint,
        ip_history=json.dumps([{"ip": ip_address, "timestamp": datetime.utcnow().isoformat()}])
    )
    db.add(session)
    db.flush()  # 获取session.id

    # ✅ 限制每个用户的session数量（最多MAX_SESSIONS_PER_USER个）
    user_sessions = db.query(Session).filter(
        Session.user_id == user.id,
        Session.revoked == False
    ).order_by(Session.created_at.desc()).all()

    if len(user_sessions) >= MAX_SESSIONS_PER_USER:
        # 撤销最旧的session
        oldest_session = user_sessions[-1]
        revoke_session(db, oldest_session.id, reason="max_sessions_exceeded")

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
        ip_address=ip_address,
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
        # 为旧token创建新session
        session = Session(
            session_id=f"migrated-{user.id}-{uuid.uuid4().hex[:8]}",
            user_id=user.id,
            username=user.username,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            first_ip=ip_address,
            current_ip=ip_address,
            device_info=device_info,
            first_device_info=device_info,
            ip_history=json.dumps([]),
            refresh_count=0
        )
        db.add(session)
        db.flush()  # 获取session.id

        # 关联旧token到新session
        old_refresh_token.session_id = session.id
        db.commit()

    # ✅ 检查IP变化
    if ip_address != session.current_ip:
        session.ip_change_count += 1
        session.current_ip = ip_address

        # 更新IP历史
        ip_history = json.loads(session.ip_history or "[]")
        ip_history.append({"ip": ip_address, "timestamp": datetime.utcnow().isoformat()})
        session.ip_history = json.dumps(ip_history[-IP_HISTORY_LIMIT:])  # 保留最近N条

        # 检测可疑活动
        if session.ip_change_count > SUSPICIOUS_IP_CHANGES:
            session.is_suspicious = True
            session.suspicious_reason = f"Excessive IP changes: {session.ip_change_count}"

    # ✅ 检查设备变化（对比User-Agent）
    if device_info != session.device_info:
        session.device_change_count += 1
        session.device_info = device_info  # 更新为最新设备
        session.device_changed = True  # 标记设备已变化

        # 检测可疑活动
        if session.device_change_count > SUSPICIOUS_DEVICE_CHANGES:
            session.is_suspicious = True
            session.suspicious_reason = f"Excessive device changes: {session.device_change_count}"

    # 增加刷新计数
    session.refresh_count += 1
    session.last_activity_at = datetime.utcnow()
    session.last_seen = datetime.utcnow()  # ✅ 更新最后活跃时间
    session.current_session_started_at = datetime.utcnow()  # ✅ 重置会话开始时间

    # ✅ 同时更新User表
    user.last_seen = datetime.utcnow()
    user.current_session_started_at = datetime.utcnow()

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
        ip_address=ip_address,
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
        session.revoked_at = datetime.utcnow()
        session.revoked_reason = reason

        # 撤销所有关联token
        db.query(RefreshToken).filter(
            RefreshToken.session_id == session_id,
            RefreshToken.revoked == False
        ).update({"revoked": True})

        db.commit()
