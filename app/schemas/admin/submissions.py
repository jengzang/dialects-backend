# schemas/admin/submissions.py
"""
管理后台 - 用户提交数据管理相关 schemas
"""

from datetime import datetime
from typing import Optional
from pydantic import ConfigDict, Field

from app.schemas.base import ShanghaiBaseModel


class InformationBase(ShanghaiBaseModel):
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

    model_config = ConfigDict(from_attributes=True)


class EditRequest(ShanghaiBaseModel):
    username: str
    created_at: str


# ===== Custom Region Admin Schemas =====

class AdminRegionCreate(ShanghaiBaseModel):
    """管理员为任意用户创建区域"""
    username: str
    region_name: str = Field(..., min_length=1, max_length=200)
    locations: list[str] = Field(..., min_items=1)
    description: Optional[str] = Field(None, max_length=1000)


class AdminRegionUpdate(ShanghaiBaseModel):
    """管理员更新任意用户的区域"""
    username: str
    region_name: str  # 当前区域名
    new_region_name: Optional[str] = Field(None, min_length=1, max_length=200)
    locations: Optional[list[str]] = Field(None, min_items=1)
    description: Optional[str] = Field(None, max_length=1000)


class AdminRegionDelete(ShanghaiBaseModel):
    """管理员删除任意用户的区域"""
    username: str
    created_at: str


class AdminRegionResponse(ShanghaiBaseModel):
    """管理员视图的区域响应"""
    id: int
    user_id: int
    username: str
    region_name: str
    locations: list[str]
    location_count: int
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class AdminRegionListResponse(ShanghaiBaseModel):
    """分页区域列表响应"""
    total: int
    skip: int
    limit: int
    data: list[AdminRegionResponse]


class UserRegionCount(ShanghaiBaseModel):
    """用户区域数量统计"""
    username: str
    region_count: int
