from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.auth.dependencies import get_current_admin_user
from app.auth.models import User, RefreshToken
from app.auth.database import get_db
from app.auth import service

router = APIRouter()


@router.get("/active")
def get_active_sessions(
    user_id: int = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """
    Get all active sessions (refresh tokens that are not revoked and not expired)

    Query params:
    - user_id: Filter by specific user (optional)
    - skip: Pagination offset
    - limit: Max results (default 100)
    """
    query = db.query(RefreshToken).filter(
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    )

    if user_id:
        query = query.filter(RefreshToken.user_id == user_id)

    total = query.count()
    tokens = query.order_by(RefreshToken.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "sessions": [
            {
                "id": token.id,
                "user_id": token.user_id,
                "username": token.user.username,
                "device_info": token.device_info,
                "created_at": token.created_at.isoformat(),
                "expires_at": token.expires_at.isoformat(),
                "is_active": not token.revoked and token.expires_at > datetime.utcnow()
            }
            for token in tokens
        ]
    }


@router.get("/user/{user_id}")
def get_user_sessions(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Get all sessions for specific user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id
    ).order_by(RefreshToken.created_at.desc()).all()

    active_tokens = [t for t in tokens if not t.revoked and t.expires_at > datetime.utcnow()]

    return {
        "user_id": user_id,
        "username": user.username,
        "total_sessions": len(tokens),
        "active_sessions": len(active_tokens),
        "sessions": [
            {
                "id": token.id,
                "device_info": token.device_info,
                "created_at": token.created_at.isoformat(),
                "expires_at": token.expires_at.isoformat(),
                "revoked": token.revoked,
                "is_expired": token.expires_at < datetime.utcnow()
            }
            for token in tokens
        ]
    }


@router.post("/revoke/{token_id}")
def revoke_session(
    token_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Revoke specific refresh token (kick user from specific device)"""
    token = db.query(RefreshToken).filter(RefreshToken.id == token_id).first()

    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    if token.revoked:
        return {"message": "Token already revoked"}

    token.revoked = True
    db.commit()

    return {
        "message": "Session revoked successfully",
        "user_id": token.user_id,
        "token_id": token_id
    }


@router.post("/revoke-user/{user_id}")
def revoke_all_user_sessions(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Revoke all refresh tokens for user (force logout all devices)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Revoke all active tokens
    revoked_count = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False
    ).update({"revoked": True})

    db.commit()

    return {
        "message": f"All sessions revoked for user {user.username}",
        "user_id": user_id,
        "revoked_count": revoked_count
    }


@router.post("/cleanup-expired")
def cleanup_expired_tokens(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Delete expired and revoked tokens from database (cleanup task)"""
    # Delete tokens that are either:
    # 1. Expired AND revoked
    # 2. Expired for more than 7 days

    from datetime import timedelta
    cleanup_threshold = datetime.utcnow() - timedelta(days=7)

    deleted_count = db.query(RefreshToken).filter(
        (RefreshToken.expires_at < datetime.utcnow()) &
        ((RefreshToken.revoked == True) | (RefreshToken.expires_at < cleanup_threshold))
    ).delete()

    db.commit()

    return {
        "message": "Expired tokens cleaned up",
        "deleted_count": deleted_count
    }


@router.get("/stats")
def get_session_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Get overall session statistics"""
    from sqlalchemy import func

    total_tokens = db.query(RefreshToken).count()
    active_tokens = db.query(RefreshToken).filter(
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    ).count()

    revoked_tokens = db.query(RefreshToken).filter(
        RefreshToken.revoked == True
    ).count()

    expired_tokens = db.query(RefreshToken).filter(
        RefreshToken.expires_at < datetime.utcnow()
    ).count()

    # Users with active sessions
    active_users = db.query(func.count(func.distinct(RefreshToken.user_id))).filter(
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    ).scalar()

    return {
        "total_tokens": total_tokens,
        "active_tokens": active_tokens,
        "revoked_tokens": revoked_tokens,
        "expired_tokens": expired_tokens,
        "active_users": active_users
    }
