"""
📦 路由模塊：處理 /api/search_chars 與 /api/search_tones 查詢音節與聲調。
"""

from fastapi import APIRouter, Request, Query, Depends
from typing import List, Optional

from app.auth.database import get_db
from app.auth.dependencies import check_api_usage_limit, get_current_user
from app.auth.models import User
from app.service.match_input_tip import match_locations_batch
from app.service.search_chars import search_characters
from common.config import CLEAR_WEEK, REQUIRE_LOGIN, DIALECTS_DB_ADMIN, DIALECTS_DB_USER, QUERY_DB_ADMIN, QUERY_DB_USER
from common.search_tones import search_tones
import time
from app.service.api_logger import *

router = APIRouter()


@router.get("/search_chars/")
async def search_chars(
        request: Request,
        chars: List[str] = Query(..., description="要查的漢字序列"),
        locations: Optional[List[str]] = Query(None, description="要查的地點，可多個"),
        regions: Optional[List[str]] = Query(None, description="要查的分區，可多個（輸入某一級的分區）"),
        region_mode: str = Query("yindian", description="分區模式，可選 'yindian' 或 'map'"),  # ✅ 加入這一行
        db: Session = Depends(get_db),
        user: Optional[User] = Depends(get_current_user)
):
    """
    - 用于 /api/search_chars 查字，返回中古地位、對應地點的讀音及注釋。
    - chars-要查的漢字序列
    - locations-要查的地點，可多個
    - regions-要查的分區，可多個（輸入某一級的分區）
    - region_mode-查詢所使用的分區欄位，可選 'yindian'（音典分區）或 'map'（地圖集二分區）
    """
    ip_address = request.client.host
    check_api_usage_limit(db, user, REQUIRE_LOGIN, ip_address=ip_address)
    update_count(request.url.path)
    start = time.time()
    try:
        locations_processed = []
        for location in locations or []:
            matched = match_locations_batch(location)
            extracted = [res[0][0] for res in matched if res[0]]
            locations_processed.extend(extracted)

        db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER

        result = search_characters(
            chars=chars,
            locations=locations_processed,
            regions=regions,
            db_path=db_path,
            region_mode=region_mode  # ✅ 傳入參數
        )
        return {"result": result}
    finally:
        duration = time.time() - start


@router.get("/search_tones/")
async def search_tones_o(
        request: Request,
        locations: Optional[List[str]] = Query(None, description="要查的地點，可多個"),
        regions: Optional[List[str]] = Query(None, description="要查的分區，可多個（輸入某一級的分區）"),
        region_mode: str = Query("yindian", description="分區模式，可選 'yindian' 或 'map'"),  # ✅ 加入這一行
        db: Session = Depends(get_db),
        user: Optional[User] = Depends(get_current_user)
):
    """
    - 用于 /api/search_tones 查調，返回調值、調類。
    - locations-要查的地點，可多個
    - regions-要查的分區，可多個（輸入某一級的分區）
    - region_mode-查詢所使用的分區欄位，可選 'yindian'（音典分區）或 'map'（地圖集二分區）
    """
    ip_address = request.client.host
    check_api_usage_limit(db, user, REQUIRE_LOGIN, ip_address=ip_address)
    update_count(request.url.path)
    start = time.time()
    try:
        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
        locations_processed = []
        for location in locations or []:
            matched = match_locations_batch(location, False, query_db=query_db)
            extracted = [res[0][0] for res in matched if res[0]]
            locations_processed.extend(extracted)

        result = search_tones(
            locations=locations_processed,
            regions=regions,
            db_path=query_db,
            region_mode=region_mode  # ✅ 傳入參數
        )
        return {"tones_result": result}
    finally:
        duration = time.time() - start
