from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CustomDataEdit(BaseModel):
    """編輯 custom 數據請求"""
    created_at: datetime  # 用於識別要編輯的記錄
    簡稱: Optional[str] = None
    音典分區: Optional[str] = None
    經緯度: Optional[str] = None
    聲韻調: Optional[str] = None
    特徵: Optional[str] = None
    值: Optional[str] = None
    說明: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    """批量刪除請求"""
    created_at_list: List[datetime]
