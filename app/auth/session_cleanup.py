"""Session和Token自动清理"""
import logging
from datetime import datetime, timedelta
from app.auth.database import SessionLocal
from app.auth.models import Session, RefreshToken
from app.auth.config import (
    SUSPICIOUS_IP_CHANGES,
    SUSPICIOUS_DEVICE_CHANGES,
    SUSPICIOUS_REFRESH_COUNT,
    MAX_TOKENS_PER_SESSION,
    TOKEN_RETENTION_DAYS
)

logger = logging.getLogger(__name__)


def cleanup_revoked_tokens():
    """
    清理7天前已撤销的refresh token
    运行频率: 每周日凌晨3:00 AM

    注意：Session表不需要清理（每个用户最多10个session，有上限控制）
    """
    logger.info("[TOKEN-CLEANUP] Starting cleanup of revoked tokens...")
    db = SessionLocal()

    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(days=TOKEN_RETENTION_DAYS)

        # 删除7天前已撤销的refresh token
        deleted_count = db.query(RefreshToken).filter(
            RefreshToken.revoked == True,
            RefreshToken.created_at < cutoff
        ).delete(synchronize_session=False)

        logger.info(f"✅ Deleted {deleted_count} revoked tokens (older than {TOKEN_RETENTION_DAYS} days)")

        db.commit()

    except Exception as e:
        logger.error(f"❌ Token cleanup failed: {e}")
        db.rollback()
    finally:
        db.close()


def cleanup_expired_sessions():
    """
    撤销已过期但未标记的session
    运行频率: 每天凌晨2:00 AM

    注意：不删除session，只标记为revoked（用于审计和统计）
    """
    logger.info("[SESSION-CLEANUP] Revoking expired sessions...")
    db = SessionLocal()

    try:
        now = datetime.utcnow()

        # 撤销已过期但未标记的session
        expired_count = db.query(Session).filter(
            Session.expires_at < now,
            Session.revoked == False
        ).update({
            "revoked": True,
            "revoked_at": now,
            "revoked_reason": "expired"
        }, synchronize_session=False)

        logger.info(f"✅ Revoked {expired_count} expired sessions")

        db.commit()

    except Exception as e:
        logger.error(f"❌ Session cleanup failed: {e}")
        db.rollback()
    finally:
        db.close()


def cleanup_suspicious_sessions():
    """
    检测并标记可疑会话
    运行频率: 每小时
    """
    db = SessionLocal()

    try:
        now = datetime.utcnow()
        flagged = 0

        # 查询活跃会话
        active_sessions = db.query(Session).filter(
            Session.revoked == False,
            Session.is_suspicious == False
        ).all()

        for session in active_sessions:
            # 规则1: IP切换次数过多
            if session.ip_change_count > SUSPICIOUS_IP_CHANGES:
                session.is_suspicious = True
                session.suspicious_reason = f"Excessive IP changes: {session.ip_change_count}"
                flagged += 1

            # 规则2: 短时间内过多刷新
            age_hours = (now - session.created_at).total_seconds() / 3600
            if age_hours < 24 and session.refresh_count > SUSPICIOUS_REFRESH_COUNT:
                session.is_suspicious = True
                session.suspicious_reason = f"Rapid refresh: {session.refresh_count} in {age_hours:.1f}h"
                flagged += 1

            # 规则3: 设备切换次数过多
            if session.device_change_count > SUSPICIOUS_DEVICE_CHANGES:
                session.is_suspicious = True
                session.suspicious_reason = f"Excessive device changes: {session.device_change_count}"
                flagged += 1

        if flagged > 0:
            logger.warning(f"⚠️  Flagged {flagged} suspicious sessions")
            db.commit()

    except Exception as e:
        logger.error(f"❌ Suspicious check failed: {e}")
        db.rollback()
    finally:
        db.close()


def cleanup_excess_tokens_per_session():
    """
    确保每个session最多保留N条token历史（删除超量的已撤销token）
    运行频率: 每天凌晨4:00 AM
    """
    db = SessionLocal()

    try:
        from sqlalchemy import func

        # 查询每个session的token数量
        sessions_with_excess = db.query(
            RefreshToken.session_id,
            func.count(RefreshToken.id).label('token_count')
        ).group_by(RefreshToken.session_id).having(
            func.count(RefreshToken.id) > MAX_TOKENS_PER_SESSION
        ).all()

        total_deleted = 0
        for session_id, count in sessions_with_excess:
            # 删除最旧的已撤销token，保留最新N条
            tokens_to_delete = db.query(RefreshToken).filter(
                RefreshToken.session_id == session_id,
                RefreshToken.revoked == True  # 只删除已撤销的token
            ).order_by(RefreshToken.created_at.asc()).limit(count - MAX_TOKENS_PER_SESSION).all()

            for token in tokens_to_delete:
                db.delete(token)
                total_deleted += 1

        db.commit()
        logger.info(f"✅ Cleaned {total_deleted} excess revoked tokens from {len(sessions_with_excess)} sessions")

    except Exception as e:
        logger.error(f"❌ Token cleanup failed: {e}")
        db.rollback()
    finally:
        db.close()
