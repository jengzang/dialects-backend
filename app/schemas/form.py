# schemas/form.py
from datetime import datetime

from pydantic import BaseModel
from typing import Optional

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
