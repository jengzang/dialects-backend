import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.path import DIALECTS_DB_ADMIN
from app.redis_client import redis_client
from app.schemas import PhonologyMatrixRequest, PhonologyClassificationMatrixRequest, PhoPieRequest
from app.service.core.matrix import (
    build_phonology_classification_matrix,
    get_all_phonology_matrices,
    build_pho_pie_by_value,
    build_pho_pie_by_status,
)
from app.sql.db_selector import get_dialects_db

router = APIRouter()


async def _fetch_phonology_matrix(locations: list[str] | None, dialects_db: str):
    """Shared implementation for GET/POST /phonology_matrix."""
    try:
        db_type = "admin" if dialects_db == DIALECTS_DB_ADMIN else "user"
        locations = locations or []

        if locations:
            sorted_locs = sorted(locations)
            locs_key = ",".join(sorted_locs)
            cache_key = f"phonology_matrix:{db_type}:{locs_key}"
        else:
            cache_key = f"phonology_matrix:{db_type}:all"

        cached_data = await redis_client.get(cache_key)
        if cached_data:
            print(f"[CACHE HIT] {cache_key}")
            return json.loads(cached_data)

        print(f"[CACHE MISS] {cache_key} - querying database")

        result = await asyncio.to_thread(
            get_all_phonology_matrices,
            locations=locations,
            db_path=dialects_db,
        )

        if not result or not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="No data found for the specified locations",
            )

        await redis_client.setex(
            cache_key,
            3600,
            json.dumps(result, ensure_ascii=False),
        )
        print(f"[CACHE SET] {cache_key}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}",
        )


@router.get("/phonology_matrix")
async def phonology_matrix(
    locations: list[str] | None = Query(None),
    dialects_db: str = Depends(get_dialects_db),
):
    """GET matrix query interface."""
    return await _fetch_phonology_matrix(locations, dialects_db)


@router.post("/phonology_matrix")
async def phonology_matrix_post(
    payload: PhonologyMatrixRequest,
    dialects_db: str = Depends(get_dialects_db),
):
    """Backward-compatible POST matrix query interface."""
    return await _fetch_phonology_matrix(payload.locations, dialects_db)


@router.post("/phonology_classification_matrix")
async def api_phonology_classification_matrix(
    payload: PhonologyClassificationMatrixRequest,
    dialects_db: str = Depends(get_dialects_db),
):
    """
    創建音韻特徵分類矩陣

    根據用戶指定的分類維度，組織音韻特徵數據。
    結合 dialects.db（現代方言讀音）和 characters.db（中古音系分類）。
    """
    # 限流和日志记录已由中间件和依赖注入自动处理

    try:
        result = await asyncio.to_thread(
            build_phonology_classification_matrix,
            locations=payload.locations,
            feature=payload.feature,
            horizontal_column=payload.horizontal_column,
            vertical_column=payload.vertical_column,
            cell_row_column=payload.cell_row_column,
            dialect_db_path=dialects_db,
            table=payload.table_name,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}",
        )


@router.post("/pho_pie_by_value")
async def api_pho_pie_by_value(
    payload: PhoPieRequest,
    dialects_db: str = Depends(get_dialects_db),
):
    """
    音值視角餅圖數據。

    固定查詢聲母、韻母、聲調三個 feature。
    每個獨特音值對應一個餅圖，扇形 = level1 各類別佔比；
    點擊扇形可取得 level2 細分。
    """
    try:
        result = await asyncio.to_thread(
            build_pho_pie_by_value,
            locations=payload.locations,
            level1_column=payload.level1_column,
            level2_column=payload.level2_column,
            dialect_db_path=dialects_db,
            table=payload.table_name,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.post("/pho_pie_by_status")
async def api_pho_pie_by_status(
    payload: PhoPieRequest,
    dialects_db: str = Depends(get_dialects_db),
):
    """
    地位視角餅圖數據。

    固定查詢聲母、韻母、聲調三個 feature。
    每個 level1 類別對應一個餅圖，扇形 = 各音值佔比；
    點擊扇形可取得該音值在 level2 的細分。
    """
    try:
        result = await asyncio.to_thread(
            build_pho_pie_by_status,
            locations=payload.locations,
            level1_column=payload.level1_column,
            level2_column=payload.level2_column,
            dialect_db_path=dialects_db,
            table=payload.table_name,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
