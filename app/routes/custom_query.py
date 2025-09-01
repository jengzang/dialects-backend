# routes/custom_query.py
"""
📦 路由模塊：處理 /api/get_custom 及 /api/get_custom_feature 查詢提交資料。
"""

from fastapi import APIRouter, Request, HTTPException, Query, Depends
from typing import List, Optional

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.custom.database import get_db as get_db_custom
from app.schemas import QueryParams, FeatureQueryParams
from app.custom.read_custom import get_from_submission
from app.service.match_input_tip import match_custom_feature
import time
from app.service.api_logger import *

router = APIRouter()


@router.get("/get_custom")
async def query_location_data(
        request: Request,
        locations: List[str] = Query(..., description="要查的地點，可多個"),
        regions: List[str] = Query(..., description="要查的音典分區，可多個"),
        need_features: List[str] = Query(..., description="要查的特徵"),
        db: Session = Depends(get_db_custom),
        user: Optional[User] = Depends(get_current_user)  # ✅ user 可為 None
):
    """
    用于 /api/get_custom 查詢用戶自定義填入的地點的相關信息用於繪圖。
    - locations-要查的地點，可多個
    - region-要查的音典分區，可多個（輸入某一級的音典分區）
    - need_features:要查的特徵
    - 返回用於繪圖的、自定義點的相關信息
    """
    query_params = QueryParams(locations=locations, regions=regions, need_features=need_features)
    update_count(request.url.path)
    log_all_fields(request.url.path, query_params.dict())
    start = time.time()
    try:
        result = get_from_submission(query_params.locations, query_params.regions, query_params.need_features, user, db)
        if not result:
            raise HTTPException(status_code=404, detail="No matching data found")
        return result
    except HTTPException:
        raise   # ✅ 让 HTTPException 保持原样传递
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        duration = time.time() - start
        log_detailed_api(request.url.path, duration, 200, request.client.host, request.headers.get("user-agent", ""),
                         request.headers.get("referer", ""))


@router.get("/get_custom_feature")
async def get_custom_feature(
        request: Request,
        locations: List[str] = Query(..., description="要查的地點，可多個"),
        regions: List[str] = Query(..., description="要查的音典分區，可多個"),
        word: str = Query(..., description="用戶輸入，待匹配特徵"),
        db: Session = Depends(get_db_custom),
        user: Optional[User] = Depends(get_current_user)  # ✅ user 可為 None
):
    """
    用于 /api/get_custom_feature 查詢用戶自定義填入的地點所含的特徵。
    - locations-要查的地點，可多個
    - region-要查的音典分區，可多個（輸入某一級的音典分區）
    - word-用戶輸入，待匹配特徵
    - 返回匹配到的自定義特徵（例如來、流等）
    """
    # print(user)
    query_params = FeatureQueryParams(locations=locations, regions=regions, word=word)
    update_count(request.url.path)
    log_all_fields(request.url.path, query_params.dict())
    start = time.time()
    try:
        result = match_custom_feature(
            query_params.locations,
            query_params.regions,
            query_params.word,
            user, db
        )
        if not result:
            raise HTTPException(status_code=404, detail="No matching features found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        duration = time.time() - start
        log_detailed_api(request.url.path, duration, 200, request.client.host, request.headers.get("user-agent", ""),
                         request.headers.get("referer", ""))
