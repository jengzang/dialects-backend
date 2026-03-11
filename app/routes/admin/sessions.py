"""
基于 RefreshToken 模型的会话管理 API（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.admin.token_service 中实现

⚠️ 注意：推荐使用新的 /admin/user-sessions/* 端点
新端点基于 Session 模型，提供更丰富的会话元数据和管理功能：
- IP 历史追踪
- 设备变更检测
- 在线时长统计
- 可疑会话标记
- 详细活动时间线

此端点保持向后兼容，但未来可能会被弃用。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.service.auth.dependencies import get_current_admin_user
from app.service.auth.models import User
from app.service.auth.database import get_db
from app.service.admin import token_service

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
    return token_service.get_active_tokens(db, user_id, skip, limit)


@router.get("/user/{user_id}")
def get_user_sessions(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Get all sessions for specific user"""
    result = token_service.get_user_tokens(db, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@router.post("/revoke/{token_id}")
def revoke_session(
    token_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Revoke specific refresh token (kick user from specific device)"""
    result = token_service.revoke_token(db, token_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    if result.get("already_revoked"):
        return {"message": result["message"]}

    return {
        "message": result["message"],
        "user_id": result["user_id"],
        "token_id": token_id
    }


@router.post("/revoke-user/{user_id}")
def revoke_all_user_sessions(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Revoke all refresh tokens for user (force logout all devices)"""
    result = token_service.revoke_user_tokens(db, user_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return {
        "message": result["message"],
        "user_id": user_id,
        "revoked_count": result["revoked_count"]
    }


@router.post("/cleanup-expired")
def cleanup_expired_tokens(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Delete expired and revoked tokens from database (cleanup task)"""
    result = token_service.cleanup_expired_tokens(db)
    return {
        "message": result["message"],
        "deleted_count": result["deleted_count"]
    }


@router.get("/stats")
def get_session_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """Get overall session statistics"""
    return token_service.get_token_stats(db)
