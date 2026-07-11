"""
Core search routes:
- /api/search_chars
- /api/search_tones
"""

import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.common.constants import VALID_CHARACTER_TABLES
from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.connection import get_db
from app.service.auth.database.models import User
from app.service.core.search_chars import search_characters
from app.service.core.search_tones import search_tones
from app.service.geo.match_input_tip import match_locations_batch_all
from app.service.user.core.database import get_db as get_custom_db
from app.service.user.submission.get_custom import get_from_submission
from app.sql.db_selector import get_dialects_db, get_query_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/search_chars/")
async def search_chars(
    chars: List[str] = Query(..., description="要查询的汉字列表，最多20个字"),
    locations: Optional[List[str]] = Query(None, description="地点列表"),
    regions: Optional[List[str]] = Query(None, description="分区列表"),
    region_mode: str = Query("yindian", description="分区模式: yindian/map"),
    table_name: str = Query("characters", description="字表名称"),
    response_mode: Literal["legacy", "compact"] = Query(
        "legacy", description="响应模式: legacy/compact"
    ),
    include_custom: bool = Query(False, description="是否附带当前用户自定义数据"),
    db: Session = Depends(get_db),
    custom_db: Session = Depends(get_custom_db),
    dialects_db: str = Depends(get_dialects_db),
    query_db: str = Depends(get_query_db),
    user: Optional[User] = Depends(get_current_user),
):
    # 按实际字符总数限制，防止通过 chars=天地 这种形式绕过数量限制
    total_char_count = sum(len(char) for char in chars)

    if total_char_count > 20:
        raise HTTPException(
            status_code=400,
            detail=f"最多只能查询20个字，当前提交了{total_char_count}个字",
        )

    if table_name not in VALID_CHARACTER_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid table_name: {table_name}. Must be one of {VALID_CHARACTER_TABLES}",
        )

    try:
        # Avoid event-loop blocking by offloading sync CPU/DB work.
        locations_processed = await run_in_threadpool(
            match_locations_batch_all,
            locations or [],
            filter_valid_abbrs_only=True,
            exact_only=True,
            query_db=query_db,
            db=None,
            user=None,
        )

        result = await run_in_threadpool(
            search_characters,
            chars=chars,
            locations=locations_processed,
            regions=regions,
            db_path=dialects_db,
            region_mode=region_mode,
            query_db_path=query_db,
            table=table_name,
            response_mode=response_mode,
        )

        tones_result = await run_in_threadpool(
            search_tones,
            locations=locations_processed,
            regions=regions,
            db_path=query_db,
            region_mode=region_mode,
        )

        custom_data = []
        if include_custom and user is not None:
            custom_data = await run_in_threadpool(
                get_from_submission,
                locations or [],
                regions,
                chars,
                user,
                custom_db,
                ["漢字"],
            )

        if response_mode == "compact":
            return {
                "result": result["result"],
                "char_meta": result["char_meta"],
                "tones_result": tones_result,
                "custom_data": custom_data,
            }

        return {
            "result": result,
            "tones_result": tones_result,
            "custom_data": custom_data,
        }
    finally:
        logger.debug("search_chars completed")

@router.get("/search_tones/")
async def search_tones_o(
    locations: Optional[List[str]] = Query(None, description="地点列表"),
    regions: Optional[List[str]] = Query(None, description="分区列表"),
    region_mode: str = Query("yindian", description="分区模式: yindian/map"),
    include_custom: bool = Query(False, description="是否附带当前用户自定义调值数据"),
    db: Session = Depends(get_db),
    custom_db: Session = Depends(get_custom_db),
    query_db: str = Depends(get_query_db),
    user: Optional[User] = Depends(get_current_user),
):
    try:
        locations_processed = await run_in_threadpool(
            match_locations_batch_all,
            locations or [],
            filter_valid_abbrs_only=False,
            exact_only=True,
            query_db=query_db,
            db=None,
            user=None,
        )
        result = await run_in_threadpool(
            search_tones,
            locations=locations_processed,
            regions=regions,
            db_path=query_db,
            region_mode=region_mode,
        )
        custom_data = []
        if include_custom and user is not None:
            custom_data = await run_in_threadpool(
                get_from_submission,
                locations or [],
                regions,
                [],
                user,
                custom_db,
                ["調值"],
            )
        return {"tones_result": result, "custom_data": custom_data}
    finally:
        logger.debug("search_tones completed")

