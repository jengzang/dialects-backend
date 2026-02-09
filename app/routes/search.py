"""
[PKG] 路由模塊：處理 /api/search_chars 與 /api/search_tones 查詢音節與聲調。
"""

from fastapi import APIRouter, Query, Depends
from typing import List, Optional
from sqlalchemy.orm import Session

from app.auth.database import get_db
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User
from app.service.match_input_tip import match_locations_batch_all
from app.service.search_chars import search_characters
from common.path import QUERY_DB_ADMIN, QUERY_DB_USER, DIALECTS_DB_ADMIN, DIALECTS_DB_USER
from app.service.search_tones import search_tones

router = APIRouter()


@router.get("/search_chars/")
async def search_chars(
        chars: List[str] = Query(..., description="要查的漢字序列"),
        locations: Optional[List[str]] = Query(None, description="要查的地點，可多個"),
        regions: Optional[List[str]] = Query(None, description="要查的分區，可多個（輸入某一級的分區）"),
        region_mode: str = Query("yindian", description="分區模式，可選 'yindian' 或 'map'"),
        db: Session = Depends(get_db),
        user: Optional[User] = Depends(ApiLimiter)  # 自动限流和日志记录
):
    """
    - 用于 /api/search_chars 查字，返回中古地位、對應地點的讀音及注釋。
    - chars-要查的漢字序列
    - locations-要查的地點，可多個
    - regions-要查的分區，可多個（輸入某一級的分區）
    - region_mode-查詢所使用的分區欄位，可選 'yindian'（音典分區）或 'map'（地圖集二分區）
    """
    # 限流和日志记录已由中间件和依赖注入自动处理
    # start = time.time()
    try:
        # [NEW] 使用批量处理函数，一次性处理所有地点
        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
        locations_processed = match_locations_batch_all(
            locations or [],
            filter_valid_abbrs_only=True,
            exact_only=True,
            query_db=query_db,
            db=db,
            user=user
        )

        db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER

        # 查询汉字读音数据
        result = search_characters(
            chars=chars,
            locations=locations_processed,
            regions=regions,
            db_path=db_path,
            region_mode=region_mode,  # [OK] 傳入參數
            query_db_path=query_db  # [NEW] 传入查询数据库路径
        )

        # 同时查询声调系统数据（避免前端二次请求）
        tones_result = search_tones(
            locations=locations_processed,
            regions=regions,
            db_path=query_db,
            region_mode=region_mode
        )

        return {
            "result": result,
            "tones_result": tones_result  # 新增：声调系统数据
        }
    finally:
        print("search_chars")
        # duration = time.time() - start
        # log_detailed_api(request.url.path, duration, 200,
        #                  request.client.host,
        #                  request.headers.get("user-agent", ""),
        #                  request.headers.get("referer", ""))

        # path = request.url.path
        # ip = request.client.host
        # agent = request.headers.get("user-agent", "")
        # referer = request.headers.get("referer", "")
        # user_id = user.id if user else None
        # log_detailed_api_to_db(db, path, duration, 200, ip, agent, referer, user_id, CLEAR_2HOUR)


@router.get("/search_tones/")
async def search_tones_o(
        locations: Optional[List[str]] = Query(None, description="要查的地點，可多個"),
        regions: Optional[List[str]] = Query(None, description="要查的分區，可多個（輸入某一級的分區）"),
        region_mode: str = Query("yindian", description="分區模式，可選 'yindian' 或 'map'"),
        db: Session = Depends(get_db),
        user: Optional[User] = Depends(ApiLimiter)  # 自动限流和日志记录
):
    """
    - 用于 /api/search_tones 查調，返回調值、調類。
    - locations-要查的地點，可多個
    - regions-要查的分區，可多個（輸入某一級的分區）
    - region_mode-查詢所使用的分區欄位，可選 'yindian'（音典分區）或 'map'（地圖集二分區）
    """
    # 限流和日志记录已由中间件和依赖注入自动处理
    # start = time.time()
    try:
        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER

        # [NEW] 使用批量处理函数，一次性处理所有地点
        locations_processed = match_locations_batch_all(
            locations or [],
            filter_valid_abbrs_only=False,
            exact_only=True,
            query_db=query_db,
            db=db,
            user=user
        )
        print(locations_processed)
        result = search_tones(
            locations=locations_processed,
            regions=regions,
            db_path=query_db,
            region_mode=region_mode  # [OK] 傳入參數
        )
        return {"tones_result": result}
    finally:
        print("search_tones")
        # duration = time.time() - start
        # log_detailed_api(request.url.path, duration, 200,
        #                  request.client.host,
        #                  request.headers.get("user-agent", ""),
        #                  request.headers.get("referer", ""))
        # 记录到数据库
        # log_detailed_api_to_db(
        #     db,
        #     request.url.path,
        #     duration,
        #     200,
        #     request.client.host,
        #     request.headers.get("user-agent", ""),
        #     request.headers.get("referer", ""),
        #     user.id if user else None,
        #     request_size=request_size,
        #     response_size=response_size,
        #     clear_old=CLEAR_2HOUR
        # )