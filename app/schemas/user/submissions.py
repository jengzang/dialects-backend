# schemas/user/submissions.py
"""
用户提交相关的 Pydantic schemas

包含：
- FormData: 用户自定义表单提交
- CustomRegion: 用户自定义区域管理
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class FormData(BaseModel):
    """
    用于 /api/submit_form 的用戶自定表單提交，寫入數據庫supplements.db。
    - locations-寫入的地點
    - region-寫入的音典分區（輸入完整的音典分區，例如嶺南-珠江-莞寶）
    - coordinates-寫入的經緯度坐標
    - phonology-寫入的聲韻調
    - feature-寫入的特徵（例如流攝等）
    - value-寫入的值（例如iu等）
    - description-寫入的具體說明
    - created_at：創建時間，submit沒有，delete必填
    - 無返回值
    """
    location: str
    region: str = None  # submit必填；delete不填
    coordinates: str = None  # submit必填；delete不填
    phonology: str = None  # submit必填；delete不填
    feature: str
    value: str
    description: Optional[str] = None  # 選填
    created_at: Optional[str] = None  # submit沒有，delete必填


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
