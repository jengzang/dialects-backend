# routes/get_coordinates.py
"""
[PKG] 路由模塊：處理 /api/get_coordinates 查詢地點座標資料。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.custom.database import get_db as get_db_custom
from app.auth.database import get_db as get_db_user
from app.schemas import CoordinatesQuery
from app.service.locs_regions import get_coordinates_from_db
from app.service.getloc_by_name_region import query_dialect_abbreviations, query_dialect_abbreviations_orm
from app.service.match_input_tip import match_locations_batch
from common.path import QUERY_DB_ADMIN, QUERY_DB_USER
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User

router = APIRouter()

@router.get("/get_coordinates")
async def get_coordinates(
        query: CoordinatesQuery = Depends(),
        db: Session = Depends(get_db_custom),
        db_user: Session = Depends(get_db_user),
        user: Optional[User] = Depends(ApiLimiter)  # 自动限流和日志记录
):
    """
    獲取坐標
    # :param region_mode: 分區模式，可選 'yindian'（音典分區）或 'map'（地圖集二分區），影響分區匹配方式
    :return: {
        "coordinates_locations": List of (簡稱, (緯度, 經度)),
        "region_mappings": {簡稱: 分區},
        "center_coordinate": [中心緯度, 中心經度] or None,
        "max_distances": {
            "lat_km": 最大緯度距離,
            "lon_km": 最大經度距離
        },
        "zoom_level": 建議地圖縮放層級
    }
    """
    # 限流和日志记录已由中间件和依赖注入自动处理

    try:
        if not query.regions.strip() and not query.locations.strip():
            raise HTTPException(status_code=400, detail="請輸入地點或簡稱！")

        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER

        locations_list = query.locations.split(',')
        regions_list = query.regions.split(',')
        locations_processed = []

        for location in locations_list:
            matched = match_locations_batch(location, query_db=query_db)
            extracted = [res[0][0] for res in matched if res[0]]
            locations_processed.extend(extracted)

        if query.iscustom and query.region_mode == 'yindian':
            # ORM 模式（對自定義表）
            abbr1 = query_dialect_abbreviations_orm(
                db, user, regions_list, locations_list
            )
            abbr2 = query_dialect_abbreviations(
                region_input=regions_list,
                location_sequence=locations_processed,
                need_storage_flag=query.flag,
                db_path=query_db,
                region_mode=query.region_mode
            )
            result = get_coordinates_from_db(
                abbr2, abbr1, use_supplementary_db=True, db_path=query_db, db=db, user=user
            )
        else:
            # 非 ORM 模式
            abbrs = query_dialect_abbreviations(
                region_input=regions_list,
                location_sequence=locations_processed,
                db_path=query_db,
                region_mode=query.region_mode
            )
            result = get_coordinates_from_db(abbrs, db_path=query_db,region_mode=query.region_mode)

        return result

    finally:
        print("get_coordinates")
