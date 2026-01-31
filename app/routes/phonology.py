# routes/phonology.py
"""
[PKG] 路由模塊：處理 /api/phonology 音韻分析請求。
不改動原邏輯，將原來 app.py 中對應接口移出。
"""

import asyncio
from typing import Optional, List

import pandas as pd
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.database import get_db
from app.auth.dependencies import get_current_user, check_api_usage_limit
from app.auth.models import User
from app.schemas import AnalysisPayload

from app.service.phonology2status import pho2sta, get_feature_counts
from app.service.status_arrange_pho import sta2pho
from app.logs.api_logger import log_all_fields
from common.config import REQUIRE_LOGIN
from common.config import DIALECTS_DB_USER, DIALECTS_DB_ADMIN, QUERY_DB_USER, QUERY_DB_ADMIN

router = APIRouter()


@router.post("/phonology")
async def api_run_phonology_analysis(
        request: Request,
        payload: AnalysisPayload,
        db: Session = Depends(get_db),
        user: Optional[User] = Depends(get_current_user),  # [OK] user 可為 None
):
    """
     - 用于 /api/phonology 路由的輸入特徵，分析聲韻。
    :param request: 傳token
    :param payload: - mode: p2s-查詢音位查詢的中古來源 s2p-按中古地位查詢音值
    - locations: 輸入地點（可多個）
    - regions: 輸入分區（某一級分區，例如嶺南，可多個）
    - features: 要查詢的特徵（聲母/韻母/聲調）必須完全匹配，用繁體字
    - status_inputs: 要查詢的中古地位，可帶類名（例如莊組），也可不帶（例如來）；
                   並且支持-全匹配（例如宕-等，會自動匹配宕一、宕三）；後端會進行簡繁轉換，可輸入簡體
                   s2p模式需要的輸入，若留空，則韻母查所有攝，聲母查三十六母，聲調查清濁+調
    - group_inputs: 分組特徵，輸入中古的類名（例如攝，則按韻攝整理某個音位）
                  可輸入簡體，支持簡體轉繁體
                   p2s模式需要的輸入，若不填，則韻母按攝分類，聲母按聲分類，聲調按清濁+調分類。
    - pho_values: 要查詢的具體音值，p2s模式下的輸入，若留空，則查所有音值
    :param db: 後端連orm
    :param user: 後端校驗得到的用戶身份
    :return: - 若為s2p,返回一個帶有地點、特徵（聲韻調）、分類值（中古地位）、值（具體音值）、對應字（所有查到的字）、
            字數、佔比（在所有查得的值中佔比）、多音字 的數組。p2s也是類似
    """
    ip_address = request.client.host  # 默认是请求的客户端 IP 地址
    check_api_usage_limit(db, user, REQUIRE_LOGIN, ip_address=ip_address)  # 限制訪問
    # update_count(request.url.path)
    log_all_fields(request.url.path, payload.dict())

    # start = time.time()
    try:
        # 根據用戶身分決定資料庫
        db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
        result = await asyncio.to_thread(run_phonology_analysis, **payload.dict(), dialects_db=db_path, query_db=query_db)
        if not result:
            raise HTTPException(status_code=400, detail="[X] 輸入的中古地位不存在")
        status = 200
        if isinstance(result, pd.DataFrame):
            return {"success": True, "results": result.to_dict(orient="records")}
        if isinstance(result, list) and all(isinstance(df, pd.DataFrame) for df in result):
            merged = pd.concat(result, ignore_index=True)
            return {"success": True, "results": merged.to_dict(orient="records")}
        return {"success": False, "error": "未識別的分析結果格式"}
    except HTTPException as http_exc:
        status = http_exc.status_code  # 抓出 status
        raise
    except Exception as e:
        status = 500
        return {"success": False, "error": str(e)}
    finally:
        print("api_run_phonology_analysis")
        # duration = time.time() - start
        # path = request.url.path
        # ip = request.client.host
        # agent = request.headers.get("user-agent", "")
        # referer = request.headers.get("referer", "")
        # user_id = user.id if user else None

        # 原有寫入 JSON 日誌
        # log_detailed_api(path, duration, status, ip, agent, referer)

        # 新增寫入資料庫
        # log_detailed_api_to_db(db, path, duration, status, ip, agent, referer, user_id, CLEAR_2HOUR)


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
        query_db=QUERY_DB_USER  # 新增：用于查询地点的数据库
):
    """
    統一介面函數：根據 mode ('s2p' 或 'p2s') 執行 sta2pho 或 pho2sta。

    參數：
        mode: 's2p' = 語音條件 ➝ 統計；'p2s' = 特徵值 ➝ 統計
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
                       region_mode=region_mode, db_path_query=query_db)

    elif mode == 'p2s':
        # if not group_inputs :
        #     raise ValueError("🔴 mode='p2s' 時，請提供 group_inputs ")
        return pho2sta(locations, regions, features, group_inputs, pho_values,
                       dialect_db_path=dialects_db, region_mode=region_mode, query_db_path=query_db)


    else:
        raise ValueError("🔴 mode 必須為 's2p' 或 'p2s'")



@router.get("/feature_counts")
async def feature_counts(
    locations: List[str] = Query(...),
    user: Optional[User] = Depends(get_current_user)  # 获取当前用户，如果未登录则为None
):
    try:
        # 根據用戶身分決定資料庫
        db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
        # print(db_path)
        # print(locations)
        result = get_feature_counts(locations, db_path)
        # 如果结果为空，可以抛出 HTTP 404 错误
        if not result:
            raise HTTPException(status_code=404, detail="No data found for the given locations.")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


