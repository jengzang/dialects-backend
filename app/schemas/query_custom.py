# schemas/query_custom.py

from pydantic import BaseModel
from typing import List

class QueryParams(BaseModel):
    """
    - 用于 /api/get_custom 查詢用戶自定義填入的地點的相關信息用於繪圖。
    - locations-要查的地點，可多個
    - region-要查的音典分區，可多個（輸入某一級的音典分區）
    - need_features:要查的特徵
    - 返回用於繪圖的、自定義點的相關信息
    """
    locations: List[str]
    regions: List[str]
    need_features: List[str]

class FeatureQueryParams(BaseModel):
    """
    - 用于 /api/get_custom_feature 查詢用戶自定義填入的地點所含的特徵。
    - locations-要查的地點，可多個
    - region-要查的音典分區，可多個（輸入某一級的音典分區）
    - word-用戶輸入，待匹配特徵
    - 返回匹配到的自定義特徵（例如來、流等）
    """
    locations: List[str]
    regions: List[str]
    word: str
