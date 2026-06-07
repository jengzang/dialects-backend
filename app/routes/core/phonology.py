# routes/phonology.py
"""
[PKG] 路由模塊：處理 /api/phonology 音韻分析請求。
不改動原邏輯，將原來 app.py 中對應接口移出。
"""

import asyncio
import json
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.sql.db_selector import get_dialects_db, get_query_db
# from app.auth.dependencies import get_current_user
# from app.logging.dependencies.limiter import ApiLimiter
# from app.auth.models import User
from app.schemas import AnalysisPayload, FeatureStatsRequest

from app.service.core.feature_stats import get_feature_counts, get_feature_statistics, generate_cache_key
from app.service.core.phonology2status import pho2sta
from app.service.core.status_arrange_pho import sta2pho
from app.common.path import QUERY_DB_USER, DIALECTS_DB_ADMIN, DIALECTS_DB_USER
from app.redis_client import redis_client

router = APIRouter()


@router.post("/phonology")
async def api_run_phonology_analysis(
        payload: AnalysisPayload,
        dialects_db: str = Depends(get_dialects_db),
        query_db: str = Depends(get_query_db)
):
    """Unified phonology analysis endpoint."""
    try:
        result = await asyncio.to_thread(
            run_phonology_analysis,
            **payload.dict(),
            dialects_db=dialects_db,
            query_db=query_db,
        )
        if not result:
            raise HTTPException(status_code=400, detail="No valid result for the requested query")

        if isinstance(result, pd.DataFrame):
            return {"success": True, "results": result.to_dict(orient="records")}

        if isinstance(result, list) and all(isinstance(df, pd.DataFrame) for df in result):
            merged = pd.concat(result, ignore_index=True)
            return {"success": True, "results": merged.to_dict(orient="records")}

        raise HTTPException(status_code=500, detail="Unexpected analysis result type")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        print("api_run_phonology_analysis")

def run_phonology_analysis(
        mode: str,
        locations: list,
        regions: list,
        features: list,
        status_inputs: list = None,
        group_inputs: list = None,
        pho_values: list = None,
        dialects_db=DIALECTS_DB_USER,
        region_mode='yindian',
        query_db=QUERY_DB_USER,
        table_name: str = "characters",
):
    """
    統一介面函數：根據 mode ('s2p' 或 'p2s') 執行 sta2pho 或 pho2sta。

    參數：
        mode: 's2p' = 語音條件 → 統計；'p2s' = 特徵值 → 統計
        locations: 方言點名稱
        features: 語音特徵欄位
        status_inputs: 語音條件字串（如 '知組三'），僅限 's2p'
        group_inputs: 要分組的欄位（如 '組聲'），僅限 'p2s'
        pho_values: 音值條件（如 ['l', 'm', 'an']），僅限 'p2s'

    回傳：
        List[pd.DataFrame]
    """

    if mode == 's2p':
        # if not status_inputs:
        #     raise ValueError("🔴 mode='s2p' 時，請提供 status_inputs。")
        return sta2pho(locations, regions, features, status_inputs, db_path_dialect=dialects_db,
                       region_mode=region_mode, db_path_query=query_db, table=table_name)

    elif mode == 'p2s':
        # if not group_inputs :
        #     raise ValueError("🔴 mode='p2s' 時，請提供 group_inputs ")
        return pho2sta(locations, regions, features, group_inputs, pho_values,
                       dialect_db_path=dialects_db, region_mode=region_mode, query_db_path=query_db,
                       table=table_name)


    else:
        raise ValueError("🔴 mode 必須為 's2p' 或 'p2s'")



@router.get("/feature_counts")
async def feature_counts(
    locations: List[str] = Query(...),
    dialects_db: str = Depends(get_dialects_db)
):
    try:
        result = get_feature_counts(locations, dialects_db)
        if not result:
            raise HTTPException(status_code=404, detail="No data found for the given locations.")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.post("/feature_stats")
async def feature_stats(
    payload: FeatureStatsRequest,
    dialects_db: str = Depends(get_dialects_db)
):
    """Get feature statistics with cache support."""
    try:
        db_type = "admin" if dialects_db == DIALECTS_DB_ADMIN else "user"

        cache_key = generate_cache_key(
            db_type=db_type,
            locations=payload.locations,
            chars=payload.chars,
            features=payload.features,
            filters=payload.filters,
        )

        try:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception:
            # Redis unavailable should not break API path
            cached_data = None

        result = await asyncio.to_thread(
            get_feature_statistics,
            locations=payload.locations,
            chars=payload.chars,
            features=payload.features,
            filters=payload.filters,
            db_path=dialects_db,
        )

        if not result or not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="No data found for the specified locations",
            )

        try:
            await redis_client.setex(
                cache_key,
                3600,
                json.dumps(result, ensure_ascii=False),
            )
        except Exception:
            # Cache write failure should not affect business response
            pass

        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
