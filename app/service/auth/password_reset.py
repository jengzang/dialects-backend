"""Short-lived reset requests; only the verified mail handler calls apply_request."""
import hashlib
import os
import secrets
import threading
from datetime import datetime, timedelta

from app.service.auth.core.utils import get_password_hash
from app.service.auth.database.models import PasswordResetRequest, User, Session, RefreshToken

RECIPIENT = '2639548777@qq.com'
TTL_SECONDS = 1800
_hash_slot = threading.BoundedSemaphore(1)


class ResetRateLimit(ValueError):
    pass


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def mailbox_enabled():
    return os.getenv('PASSWORD_RESET_ENABLED', '').lower() == 'true' and bool(
        os.getenv('PASSWORD_RESET_IMAP_PASSWORD', '').strip()
    )


def create_request(db, email, password, ip, *, now=None):
    now = now or datetime.utcnow()
    if len(password) < 6 or len(password.encode('utf-8')) > 72:
        raise ValueError('Password must contain at least 6 characters and at most 72 UTF-8 bytes')
    if not _hash_slot.acquire(blocking=False):
        raise ResetRateLimit('Password recovery is busy; try again shortly')
    # Reserve admission under a short write lock; bcrypt runs after releasing it.
    try:
        if db.bind.dialect.name == 'sqlite':
            db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        db.query(PasswordResetRequest).filter(
            PasswordResetRequest.created_at < now - timedelta(hours=1)
        ).delete(synchronize_session=False)
        window = db.query(PasswordResetRequest).filter(
            PasswordResetRequest.created_at > now - timedelta(minutes=10)
        )
        if (window.filter(PasswordResetRequest.email == email).count() >= 3
                or window.filter(PasswordResetRequest.ip == ip).count() >= 10
                or window.count() >= 100):
            raise ResetRateLimit('Too many password reset requests; try again in 10 minutes')
        user = db.query(User).filter(User.email == email).first()
        token = secrets.token_urlsafe(32)
        db.add(PasswordResetRequest(
            token_hash=digest(token), user_id=user.id if user else None,
            email=email, ip=ip,
            credential_digest=digest(user.hashed_password) if user else None,
            created_at=now, expires_at=now + timedelta(seconds=TTL_SECONDS),
        ))
        db.commit()
        password_hash = get_password_hash(password)
        db.query(PasswordResetRequest).filter(
            PasswordResetRequest.token_hash == digest(token),
            PasswordResetRequest.user_id.isnot(None),
        ).update({'password_hash': password_hash}, synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        _hash_slot.release()
    return {'request_id': token, 'expires_in': TTL_SECONDS, 'recipient': RECIPIENT}


def apply_request(db, token, sender, *, now=None):
    """Caller must authenticate raw mail before passing its unique From address."""
    now = now or datetime.utcnow()
    try:
        row = db.get(PasswordResetRequest, digest(token))
        if (not row or not row.password_hash or row.consumed_at or row.expires_at <= now
                or row.email != sender or row.user_id is None):
            db.rollback()
            return False
        user = db.get(User, row.user_id)
        if (not user or user.email != sender or user.status != 'active'
                or digest(user.hashed_password) != row.credential_digest):
            db.rollback()
            return False
        claimed = db.query(PasswordResetRequest).filter(
            PasswordResetRequest.token_hash == row.token_hash,
            PasswordResetRequest.consumed_at.is_(None),
        ).update({'consumed_at': now}, synchronize_session=False)
        changed = db.query(User).filter(
            User.id == user.id, User.hashed_password == user.hashed_password,
            User.email == sender, User.status == 'active',
        ).update({'hashed_password': row.password_hash, 'failed_attempts': 0,
                  'last_failed_login': None}, synchronize_session=False)
        if claimed != 1 or changed != 1:
            db.rollback()
            return False
        db.query(Session).filter(Session.user_id == user.id, Session.revoked.is_(False)).update(
            {'revoked': True, 'revoked_at': now, 'revoked_reason': 'password_reset'},
            synchronize_session=False,
        )
        db.query(RefreshToken).filter(RefreshToken.user_id == user.id).update(
            {'revoked': True}, synchronize_session=False,
        )
        db.query(PasswordResetRequest).filter(PasswordResetRequest.user_id == user.id).update(
            {'consumed_at': now, 'password_hash': None, 'credential_digest': None},
            synchronize_session=False,
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
