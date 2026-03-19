from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.schemas.core.phonology import CharListRequest, YinWeiAnalysis, ZhongGuAnalysis
from app.service.core.new_pho import (
    _run_dialect_analysis_sync,
    generate_cache_key,
    get_cache,
    process_chars_status,
    set_cache,
)
from app.service.core.phonology2status import pho2sta
from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.models import User
from app.service.user.core.database import get_db as get_custom_db
from app.service.user.submission.get_custom import get_from_submission
from app.sql.db_selector import get_dialects_db, get_query_db

router = APIRouter()


@router.post("/charlist")
async def generate_combinations_and_query(payload: CharListRequest) -> List[Dict]:
    path_strings = payload.path_strings
    column = payload.column
    combine_query = payload.combine_query
    table_name = payload.table_name

    cache_key = generate_cache_key(
        path_strings,
        column,
        combine_query,
        exclude_columns=payload.exclude_columns,
        table=table_name,
    )

    cached_result = await get_cache(cache_key)
    if cached_result is not None:
        return cached_result

    result = await run_in_threadpool(
        process_chars_status,
        path_strings,
        column,
        combine_query,
        payload.exclude_columns,
        table_name,
    )

    if result:
        await set_cache(cache_key, result, expire_seconds=600)

    return result


@router.post("/ZhongGu")
async def analyze_zhonggu(
    payload: ZhongGuAnalysis,
    dialects_db: str = Depends(get_dialects_db),
    query_db: str = Depends(get_query_db),
    user: Optional[User] = Depends(get_current_user),
    custom_db: Session = Depends(get_custom_db),
):
    char_request_payload = CharListRequest(
        path_strings=payload.path_strings,
        column=payload.column,
        combine_query=payload.combine_query,
        exclude_columns=payload.exclude_columns,
        table_name=payload.table_name,
    )
    cached_char_result = await generate_combinations_and_query(payload=char_request_payload)

    if not cached_char_result:
        return {"status": "empty", "message": "無符合條件的漢字", "data": [], "custom_data": []}

    analysis_results = await run_in_threadpool(
        _run_dialect_analysis_sync,
        char_data_list=cached_char_result,
        locations=payload.locations,
        regions=payload.regions,
        features=payload.features,
        region_mode=payload.region_mode,
        db_path_dialect=dialects_db,
        db_path_query=query_db,
    )

    custom_data = []
    if payload.include_custom and user is not None:
        need_features = [item["query"] for item in cached_char_result if item.get("query")]
        if need_features:
            custom_data = await run_in_threadpool(
                get_from_submission,
                payload.locations,
                payload.regions,
                need_features,
                user,
                custom_db,
            )

    return {
        "status": "success",
        "data": analysis_results,
        "custom_data": custom_data,
    }


@router.post("/YinWei")
async def analyze_yinwei(
    payload: YinWeiAnalysis,
    dialects_db: str = Depends(get_dialects_db),
    query_db: str = Depends(get_query_db),
):
    try:
        analysis_results = await run_in_threadpool(
            pho2sta,
            locations=payload.locations,
            regions=payload.regions,
            features=payload.features,
            status_inputs=payload.group_inputs,
            pho_values=payload.pho_values,
            region_mode=payload.region_mode,
            dialect_db_path=dialects_db,
            exclude_columns=payload.exclude_columns,
            query_db_path=query_db,
            table=payload.table_name,
        )

        if isinstance(analysis_results, pd.DataFrame):
            return {"success": True, "results": analysis_results.to_dict(orient="records")}

        if isinstance(analysis_results, list) and all(isinstance(df, pd.DataFrame) for df in analysis_results):
            if not analysis_results:
                return {"success": True, "results": []}
            merged = pd.concat(analysis_results, ignore_index=True)
            return {"success": True, "results": merged.to_dict(orient="records")}

        return {"success": False, "error": "Unexpected analysis result format"}
    except Exception as e:
        return {"success": False, "error": str(e)}
