from typing import Optional, List, Dict

import pandas as pd
from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_user
# from app.logging.dependencies.limiter import ApiLimiter
from app.auth.models import User
from app.schemas.phonology import CharListRequest, ZhongGuAnalysis, YinWeiAnalysis

from app.service.new_pho import process_chars_status, set_cache, get_cache, generate_cache_key, \
    _run_dialect_analysis_sync
from app.service.phonology2status import pho2sta
from app.common.path import QUERY_DB_ADMIN, QUERY_DB_USER, DIALECTS_DB_ADMIN, DIALECTS_DB_USER

router = APIRouter()


@router.post("/charlist")
async def generate_combinations_and_query(
        payload: CharListRequest,  # 自动限流和日志记录
) -> List[Dict]:
    path_strings = payload.path_strings
    column = payload.column
    combine_query = payload.combine_query

    # 限流和日志记录已由中间件和依赖注入自动处理

    # 2. 生成緩存 Key
    cache_key = generate_cache_key(path_strings, column, combine_query, exclude_columns=payload.exclude_columns)

    # 3. 【嘗試讀取緩存】
    # [OK] 加上 await
    cached_result = await get_cache(cache_key)
    if cached_result is not None:
        return cached_result
    # print("🐢 No Cache, computing...")

    # 這裡的 process_chars_status 依然是同步函數，沒關係，計算完再異步存緩存
    # 注意：如果 process_chars_status 裡有數據庫操作，建議確保它是高效的
    # 或者是用 run_in_executor 放到線程池裡跑，防止阻塞 async loop
    result = process_chars_status(path_strings, column, combine_query, exclude_columns=payload.exclude_columns)

    if result:
        # [OK] 加上 await
        await set_cache(cache_key, result, expire_seconds=600)

    return result


@router.post("/ZhongGu")
async def analyze_zhonggu(
        payload: ZhongGuAnalysis,
        user: Optional[User] = Depends(get_current_user)  # 自动限流和日志记录
):
    """
    全新的接口：
    1. Await 緩存接口獲取漢字
    2. 調用同步函數分析方言
    """
    # 限流和日志记录已由中间件和依赖注入自动处理

    # 1. 獲取漢字 (Step 1)
    char_request_payload = CharListRequest(
        path_strings=payload.path_strings,
        column=payload.column,
        combine_query=payload.combine_query,
        exclude_columns=payload.exclude_columns
    )
    cached_char_result = await generate_combinations_and_query(
        payload=char_request_payload,
        user=user,
    )

    if not cached_char_result:
        return {"status": "empty", "message": "無符合條件的漢字", "data": []}

    # 2. 方言分析 (Step 2)
    # 直接從 payload 取出第二部分的參數
    locations = payload.locations
    regions = payload.regions
    features = payload.features
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
    query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
    analysis_results = await run_in_threadpool(
        _run_dialect_analysis_sync,
        char_data_list=cached_char_result,
        locations=locations,
        regions=regions,
        features=features,
        region_mode=payload.region_mode,  # 如果需要的話
        db_path_dialect=db_path,
        db_path_query=query_db  # 新增：传入查询数据库
    )

    return {
        "status": "success",
        "data": analysis_results
    }


@router.post("/YinWei")
async def analyze_yinwei(
        payload: YinWeiAnalysis,
        user: Optional[User] = Depends(get_current_user)  # 自动限流和日志记录
):
    # 限流和日志记录已由中间件和依赖注入自动处理

    try:
        locations = payload.locations
        regions = payload.regions
        features = payload.features
        db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
        analysis_results = await run_in_threadpool(
            pho2sta,
            locations=locations,
            regions=regions,
            features=features,
            status_inputs=payload.group_inputs,
            pho_values=payload.pho_values,
            region_mode=payload.region_mode,  # 如果需要的話
            dialect_db_path=db_path,
            exclude_columns=payload.exclude_columns,
            query_db_path=query_db  # 新增：传入查询数据库
        )
        if isinstance(analysis_results, pd.DataFrame):
            return {"success": True, "results": analysis_results.to_dict(orient="records")}
        if isinstance(analysis_results, list) and all(isinstance(df, pd.DataFrame) for df in analysis_results):
            merged = pd.concat(analysis_results, ignore_index=True)
            return {"success": True, "results": merged.to_dict(orient="records")}
        return {"success": False, "error": "未識別的分析結果格式"}
    except Exception as e:
        return {"success": False, "error": str(e)}
