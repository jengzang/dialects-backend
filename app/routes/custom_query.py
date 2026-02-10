# routes/custom_query.py
"""
[PKG] 路由模塊：處理 /api/get_custom 及 /api/get_custom_feature 查詢提交資料。
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.custom.database import get_db as get_db_custom
from app.schemas import QueryParams, FeatureQueryParams
from app.custom.read_custom import get_from_submission
from app.service.match_input_tip import match_custom_feature
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User

router = APIRouter()


@router.get("/get_custom")
async def query_location_data(
        locations: List[str] = Query(..., description="要查的地點，可多個"),
        regions: List[str] = Query(..., description="要查的分區，可多個"),
        need_features: str = Query(..., description="要查的特徵，用逗號分隔（例如：流,深）"),
        db: Session = Depends(get_db_custom),
        user: Optional[User] = Depends(ApiLimiter)  # 自动限流和日志记录
):
    """
    用于 /api/get_custom 查詢用戶自定義填入的地點的相關信息用於繪圖。
    - locations-要查的地點，可多個
    - region-要查的音典分區，可多個（輸入某一級的音典分區）
    - need_features:要查的特徵，用逗號分隔（例如：流,深）
    - 返回用於繪圖的、自定義點的相關信息
    """
    # 限流和日志记录已由中间件和依赖注入自动处理
    # [OK] 将逗号分隔的字符串分割成列表
    features_list = [f.strip() for f in need_features.split(',') if f.strip()]

    query_params = QueryParams(locations=locations, regions=regions, need_features=features_list)
    try:
        result = get_from_submission(query_params.locations, query_params.regions, query_params.need_features, user, db)
        return result if result else []  # [OK] 返回空数组而不是 404 错误
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        print("query_location_data")


@router.get("/get_custom_feature")
async def get_custom_feature(
        locations: List[str] = Query(..., description="要查的地點，可多個"),
        regions: List[str] = Query(..., description="要查的音典分區，可多個"),
        word: str = Query(..., description="用戶輸入，待匹配特徵"),
        db: Session = Depends(get_db_custom),
        user: Optional[User] = Depends(ApiLimiter)  # 自动限流和日志记录
):
    """
    用于 /api/get_custom_feature 查詢用戶自定義填入的地點所含的特徵。
    - locations-要查的地點，可多個
    - region-要查的音典分區，可多個（輸入某一級的音典分區）
    - word-用戶輸入，待匹配特徵
    - 返回匹配到的自定義特徵（例如來、流等）
    """
    # 限流和日志记录已由中间件和依赖注入自动处理
    query_params = FeatureQueryParams(locations=locations, regions=regions, word=word)
    try:
        result = match_custom_feature(
            query_params.locations,
            query_params.regions,
            query_params.word,
            user, db
        )
        return result if result else []  # [OK] 返回空数组而不是 404 错误
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        print("get_custom_feature")
