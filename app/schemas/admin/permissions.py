# schemas/admin/permissions.py
"""
管理后台 - 权限管理相关 schemas
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PermissionBase(BaseModel):
    """权限基础模型"""
    user_id: int
    username: str
    db_key: str
    can_write: bool = False

    class Config:
        from_attributes = True


class PermissionCreate(BaseModel):
    """创建权限请求"""
    user_id: int
    db_key: str
    can_write: bool = False


class PermissionUpdate(BaseModel):
    """更新权限请求"""
    can_write: bool


class PermissionResponse(PermissionBase):
    """权限响应模型"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserWithPermissions(BaseModel):
    """带权限的用户信息"""
    id: int
    username: str
    email: str
    role: str
    permissions: list[PermissionResponse] = []

    class Config:
        from_attributes = True
