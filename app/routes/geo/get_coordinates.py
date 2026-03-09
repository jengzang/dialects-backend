# routes/get_coordinates.py
"""
Route module for /api/get_coordinates.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.custom.database import SessionLocal
from app.schemas import CoordinatesQuery
from app.service.locs_regions import get_coordinates_from_db
from app.service.getloc_by_name_region import query_dialect_abbreviations, query_dialect_abbreviations_orm
from app.service.match_input_tip import match_locations_batch_all
from app.auth.dependencies import get_current_user
from app.sql.db_selector import get_query_db
from app.auth.models import User

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
        raise HTTPException(status_code=401, detail="Authentication required for custom coordinates")

    locations_list = query.locations.split(',')
    regions_list = query.regions.split(',')

    # Batch exact-match locations to avoid per-item loops.
    locations_processed = match_locations_batch_all(
        locations_list,
        filter_valid_abbrs_only=True,
        exact_only=True,
        query_db=query_db
    )

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
