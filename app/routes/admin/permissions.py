from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.auth.database import get_db
from app.auth.dependencies import get_current_admin_user
from app.auth.models import User, UserDbPermission
from app.schemas.admin import (
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
    UserWithPermissions
)

router = APIRouter()


@router.get("/permissions", response_model=List[PermissionResponse])
def get_all_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取所有权限记录

    权限要求：管理员
    """
    permissions = db.query(UserDbPermission).all()
    return permissions


@router.get("/permissions/user/{user_id}", response_model=List[PermissionResponse])
def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取特定用户的所有权限

    权限要求：管理员
    """
    # 检查用户是否存在
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    permissions = db.query(UserDbPermission).filter(
        UserDbPermission.user_id == user_id
    ).all()
