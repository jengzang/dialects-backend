from pydantic import BaseModel
from typing import List, Optional

class CoordinatesQuery(BaseModel):
    """
    - 用于 /api/get_coordinates 查詢地點座標資料。
    - regions: 音典分區，可多個
    - locations: 地點簡稱，可多個
    - iscustom: 是否讀取用戶自定義數據庫,若為真則讀取
    - flag: 查所有點or只查有字表的點（True = 只查有字表的）
    """
    regions: str
    locations: str
    region_mode: str = "yindian"
    iscustom: Optional[bool] = None
    flag: bool = True
