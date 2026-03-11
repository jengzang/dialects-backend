# schemas/admin/users.py
"""
管理后台 - 用户管理相关 schemas
"""

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


class UserListItem(BaseModel):
    """轻量级用户列表项（仅包含基本信息）"""
    id: int
    username: str
    email: EmailStr
    role: str

    class Config:
        from_attributes = True


class ApiUsageLog(BaseModel):
    id: int
    user_id: Optional[int]
    path: str
    duration: float
    status_code: int
    ip: Optional[str]
    ip_location: Optional[str] = None
    user_agent: Optional[str]
    referer: Optional[str]
    called_at: datetime

    class Config:
        from_attributes = True
