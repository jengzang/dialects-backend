from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    username: str
    email: str
    role: Optional[str] = "user"
    status: Optional[str] = "active"


class UserUpdate(UserBase):
    pass


class User(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApiUsageLog(BaseModel):
    id: int
    user_id: Optional[int]
    path: str
    duration: float
    status_code: int
    ip: Optional[str]
    user_agent: Optional[str]
    referer: Optional[str]
    called_at: datetime

    class Config:
        from_attributes = True


class UserUpdateSchema(BaseModel):
    username: Optional[str] = None  # 用戶名是可選的
    email: Optional[EmailStr] = None  # 郵箱是可選的

    class Config:
        from_attributes = True


class AdminCreate(BaseModel):
    username: str
    email: EmailStr
    password: Optional[str]  # 显式包含 password 字段
    role: Optional[str] = "user"  # 默認是普通用戶，管理員角色可以設為 'admin'

    class Config:
        from_attributes = True


class InformationBase(BaseModel):
    簡稱: str
    音典分區: str
    經緯度: str
    聲韻調: str
    特徵: str
    值: str
    說明: Optional[str]  # 這樣就允許說明為 None
    username: str
    user_id: Optional[int] = None  # 后端自动填充，不需要用户传递
    created_at: Optional[datetime] = None  # 后端自动生成

    class Config:
        from_attributes = True


class EditRequest(BaseModel):
    username: str
    created_at: str


class UpdatePassword(BaseModel):
    username: str  # 用戶名是可選的
    password: str

    class Config:
        from_attributes = True


class LetAdmin(BaseModel):
    username: str
    role: str = Field(default="")

    class Config:
        from_attributes = True


# 权限管理相关 Schema
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
