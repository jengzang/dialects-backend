"""
[PKG] 路由模塊：處理 /api/get_locs 查詢地點。
"""

from fastapi import APIRouter, Query
from typing import List, Optional

from app.service.match_input_tip import match_locations_batch
from common.config import QUERY_DB_ADMIN, QUERY_DB_USER
from common.getloc_by_name_region import query_dialect_abbreviations
from app.logs.api_logger import *

router = APIRouter()


@router.get("/get_locs/")
async def get_all_locs(
        request: Request,
        locations: Optional[List[str]] = Query(None, description="要查的地點，可多個"),
        regions: Optional[List[str]] = Query(None, description="要查的分區，可多個（輸入某一級的分區）"),
        region_mode: str = Query("yindian", description="分區模式，yindian 或 map"),  # [OK] 加上這行
        user: Optional[User] = Depends(get_current_user)
):
    """
    - 用于 /api/get_locs 查匹配的地點（分區+地點），返回地點序列。
    - locations-要查的地點，可多個
    - regions-要查的分區，可多個（輸入某一級的分區）
    - region_mode-使用的分區
    """
    # update_count(request.url.path)
    log_all_fields(request.url.path, {"locations": locations, "regions": regions})
    # start = time.time()
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
        # duration = time.time() - start
        # log_detailed_api(
        #     request.url.path, duration, 200,
        #     request.client.host,
        #     request.headers.get("user-agent", ""),
        #     request.headers.get("referer", "")
        # )

