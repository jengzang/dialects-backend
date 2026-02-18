# schemas/custom_region.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class CustomRegionCreate(BaseModel):
    """创建或更新自定义区域的请求模型"""
    region_name: str = Field(..., min_length=1, max_length=200, description="区域名称")
    locations: List[str] = Field(..., min_items=1, description="地点简称列表")
    description: Optional[str] = Field(None, max_length=1000, description="区域描述")

    @field_validator('locations')
    @classmethod
    def validate_locations(cls, v):
        """验证地点列表"""
        if not v:
            raise ValueError("地点列表不能为空")
        # 验证每个地点长度
        for loc in v:
            if not loc or len(loc) > 100:
                raise ValueError(f"地点名称无效: {loc}")
        return v


class CustomRegionResponse(BaseModel):
    """自定义区域响应模型"""
    id: int
    region_name: str
    locations: List[str]
    location_count: int
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomRegionList(BaseModel):
    """自定义区域列表响应模型"""
    success: bool = True
    regions: List[CustomRegionResponse]
    total: int
