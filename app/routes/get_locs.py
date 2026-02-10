"""
[PKG] 路由模塊：處理 /api/get_locs 查詢地點。
"""

from fastapi import APIRouter, Query, Depends
from typing import List, Optional

from app.service.match_input_tip import match_locations_batch
from common.path import QUERY_DB_ADMIN, QUERY_DB_USER
from app.service.getloc_by_name_region import query_dialect_abbreviations
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User

router = APIRouter()


@router.get("/get_locs/")
async def get_all_locs(
        locations: Optional[List[str]] = Query(None, description="要查的地點，可多個"),
        regions: Optional[List[str]] = Query(None, description="要查的分區，可多個（輸入某一級的分區）"),
        region_mode: str = Query("yindian", description="分區模式，yindian 或 map"),  # [OK] 加上這行
        user: Optional[User] = Depends(ApiLimiter)  # 自动限流和日志记录
):
    """
    - 用于 /api/get_locs 查匹配的地點（分區+地點），返回地點序列。
    - locations-要查的地點，可多個
    - regions-要查的分區，可多個（輸入某一級的分區）
    - region_mode-使用的分區
    """
    # 限流和日志记录已由中间件和依赖注入自动处理
    try:
        locations_processed = []
        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
        for location in locations or []:
            matched = match_locations_batch(location, query_db=query_db)
            extracted = [res[0][0] for res in matched if res[0]]
            locations_processed.extend(extracted)

        # [OK] 加入 region_mode 傳入查詢函數
        result = query_dialect_abbreviations(
            region_input=regions,
            location_sequence=locations_processed,
            db_path=query_db,
            region_mode=region_mode
        )
        return {"locations_result": result}
    finally:
        print("get_all_loc")

