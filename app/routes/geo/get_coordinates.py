# routes/get_coordinates.py
"""
Route module for /api/get_coordinates.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.service.user.core.database import SessionLocal
from app.schemas import CoordinatesQuery
from app.service.geo.locs_regions import get_coordinates_from_db
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations, query_dialect_abbreviations_orm
from app.service.geo.match_input_tip import match_locations_batch_exact
from app.service.auth.core.dependencies import get_current_user
from app.sql.db_selector import get_query_db
from app.service.auth.database.models import User

router = APIRouter()


@router.get("/get_coordinates")
async def get_coordinates(
        query: CoordinatesQuery = Depends(),
        query_db: str = Depends(get_query_db),
        user: Optional[User] = Depends(get_current_user)
):
    try:
        if not query.regions.strip() and not query.locations.strip():
            raise HTTPException(status_code=400, detail="至少传入一个地点")

        result = await run_in_threadpool(
            _resolve_coordinates_sync,
            query,
            query_db,
            user
        )
        return result
    finally:
        print("get_coordinates")


def _resolve_coordinates_sync(
        query: CoordinatesQuery,
        query_db: str,
        user: Optional[User]
):
    if query.iscustom and not user:
        # 未登錄時靜默降級：不查自定義數據，走普通流程
        query.iscustom = False

    locations_list = query.locations.split(',')
    regions_list = query.regions.split(',')

    locations_processed = []
    for location in locations_list:
        matched = match_locations_batch_exact(location, query_db=query_db)
        extracted = [res[0][0] for res in matched if res[0]]
        locations_processed.extend(extracted)

    if query.iscustom and query.region_mode == 'yindian':
        thread_db: Optional[Session] = None
        try:
            thread_db = SessionLocal()
            abbr_custom = query_dialect_abbreviations_orm(
                thread_db, user, regions_list, locations_list
            )
            abbr_main = query_dialect_abbreviations(
                region_input=regions_list,
                location_sequence=locations_processed,
                need_storage_flag=query.flag,
                db_path=query_db,
                region_mode=query.region_mode
            )
            return get_coordinates_from_db(
                abbr_main,
                abbr_custom,
                use_supplementary_db=True,
                db_path=query_db,
                db=thread_db,
                user=user
            )
        finally:
            if thread_db is not None:
                thread_db.close()

    abbrs = query_dialect_abbreviations(
        region_input=regions_list,
        location_sequence=locations_processed,
        db_path=query_db,
        region_mode=query.region_mode
    )
    return get_coordinates_from_db(abbrs, db_path=query_db, region_mode=query.region_mode)
