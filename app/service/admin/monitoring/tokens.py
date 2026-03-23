"""
Token管理业务逻辑层（基于RefreshToken模型）

职责：
- 查询活跃token
- Token统计
- 撤销token
- 清理过期token

注意：此模块不依赖FastAPI，可在任何地方调用
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.service.auth.database.models import User, RefreshToken
from app.common.time_utils import to_shanghai_iso


def get_active_tokens(
    db: Session,
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> Dict[str, Any]:
    """
    获取所有活跃的token（未撤销且未过期）

    Args:
        db: 数据库会话
        user_id: 过滤特定用户（可选）
        skip: 分页偏移
        limit: 最大结果数

    Returns:
        包含total和sessions的字典
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
                "created_at": to_shanghai_iso(token.created_at),
                "expires_at": to_shanghai_iso(token.expires_at),
                "is_active": not token.revoked and token.expires_at > datetime.utcnow()
            }
            for token in tokens
        ]
    }


def get_user_tokens(db: Session, user_id: int) -> Dict[str, Any]:
    """
    获取特定用户的所有token

    Args:
        db: 数据库会话
        user_id: 用户ID

    Returns:
        用户token信息字典，如果用户不存在则返回None
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

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
                "created_at": to_shanghai_iso(token.created_at),
                "expires_at": to_shanghai_iso(token.expires_at),
                "revoked": token.revoked,
                "is_expired": token.expires_at < datetime.utcnow()
            }
            for token in tokens
        ]
    }


def revoke_token(db: Session, token_id: int) -> Dict[str, Any]:
    """
    撤销特定token

    Args:
        db: 数据库会话
        token_id: Token ID

    Returns:
        结果字典
    """
    token = db.query(RefreshToken).filter(RefreshToken.id == token_id).first()

    if not token:
        return {
            "success": False,
            "error": "Token not found"
        }

    if token.revoked:
        return {
            "success": True,
            "message": "Token already revoked",
            "already_revoked": True
        }

    token.revoked = True
    db.commit()

    return {
        "success": True,
        "message": "Session revoked successfully",
        "user_id": token.user_id,
        "token_id": token_id
    }


def revoke_user_tokens(db: Session, user_id: int) -> Dict[str, Any]:
    """
    撤销用户的所有token（强制登出所有设备）

    Args:
        db: 数据库会话
        user_id: 用户ID

    Returns:
        结果字典
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {
            "success": False,
            "error": "User not found"
        }

    # 撤销所有活跃token
    revoked_count = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False
    ).update({"revoked": True})

    db.commit()

    return {
        "success": True,
        "message": f"All sessions revoked for user {user.username}",
        "user_id": user_id,
        "revoked_count": revoked_count
    }


def cleanup_expired_tokens(db: Session) -> Dict[str, Any]:
    """
    清理过期和已撤销的token

    删除满足以下条件的token：
    1. 已过期且已撤销
    2. 过期超过7天

    Args:
        db: 数据库会话

    Returns:
        结果字典
    """
    cleanup_threshold = datetime.utcnow() - timedelta(days=7)

    deleted_count = db.query(RefreshToken).filter(
        (RefreshToken.expires_at < datetime.utcnow()) &
        ((RefreshToken.revoked == True) | (RefreshToken.expires_at < cleanup_threshold))
    ).delete()

    db.commit()

    return {
        "success": True,
        "message": "Expired tokens cleaned up",
        "deleted_count": deleted_count
    }


def get_token_stats(db: Session) -> Dict[str, Any]:
    """
    获取token统计信息

    Args:
        db: 数据库会话

    Returns:
        统计信息字典
    """
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

    # 拥有活跃会话的用户数
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
