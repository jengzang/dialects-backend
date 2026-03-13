import asyncio
import json

from fastapi import Depends, HTTPException

from app.common.path import DIALECTS_DB_ADMIN
from app.redis_client import redis_client
from app.routes.core.phonology import router
from app.schemas import PhonologyMatrixRequest, PhonologyClassificationMatrixRequest
from app.service.core.matrix import build_phonology_classification_matrix, get_all_phonology_matrices
from app.sql.db_selector import get_dialects_db


@router.post("/phonology_matrix")
async def phonology_matrix(
    payload: PhonologyMatrixRequest,
    dialects_db: str = Depends(get_dialects_db)
):
    """
    获取指定地点的声母-韵母-汉字交叉表数据

    Request Body:
    {
        "locations": ["東莞莞城", "雲浮富林"]  // 可選，不傳則獲取所有地點
    }

    返回格式适合前端生成表格：
    - 横坐标：声母
    - 纵坐标：韵母
    - 表内显示：按声调分行的汉字
    """
    # 限流和日志记录已由中间件和依赖注入自动处理

    try:
        # 数据库路径已通过依赖注入自动选择
        # 根据数据库路径判断类型（用于缓存键）
        db_type = "admin" if dialects_db == DIALECTS_DB_ADMIN else "user"

        locations = payload.locations

        # 構建緩存鍵（包含地點信息）
        if locations and len(locations) > 0:
            # 對地點列表排序以確保緩存鍵一致
            sorted_locs = sorted(locations)
            locs_key = ",".join(sorted_locs)
            cache_key = f"phonology_matrix:{db_type}:{locs_key}"
        else:
            # 獲取所有地點
            cache_key = f"phonology_matrix:{db_type}:all"

        # 尝试从 Redis 获取缓存
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            print(f"[CACHE HIT] {cache_key}")
            return json.loads(cached_data)

        print(f"[CACHE MISS] {cache_key} - 查询数据库")

        # 从数据库查询
        result = await asyncio.to_thread(
            get_all_phonology_matrices,
            locations=locations,
            db_path=dialects_db
        )

        if not result or not result.get("data"):
            raise HTTPException(
                status_code=404,
                detail="No data found for the specified locations"
            )

        # 存入 Redis 缓存（1小时过期）
        await redis_client.setex(
            cache_key,
            3600,  # 1小时
            json.dumps(result, ensure_ascii=False)
        )
        print(f"[CACHE SET] {cache_key}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )


@router.post("/phonology_classification_matrix")
async def api_phonology_classification_matrix(
    payload: PhonologyClassificationMatrixRequest,
    dialects_db: str = Depends(get_dialects_db)
):
    """
    創建音韻特徵分類矩陣

    根據用戶指定的分類維度，組織音韻特徵數據。
    結合 dialects.db（現代方言讀音）和 characters.db（中古音系分類）。
    """
    # 限流和日志记录已由中间件和依赖注入自动处理

    try:
        # 数据库路径已通过依赖注入自动选择

        # 在線程池中運行（避免阻塞）
        result = await asyncio.to_thread(
            build_phonology_classification_matrix,
            locations=payload.locations,
            feature=payload.feature,
            horizontal_column=payload.horizontal_column,
            vertical_column=payload.vertical_column,
            cell_row_column=payload.cell_row_column,
            dialect_db_path=dialects_db
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )
