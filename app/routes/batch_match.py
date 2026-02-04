# routes/batch_match.py
"""
[PKG] 路由模塊：處理 /api/batch_match 地點名稱匹配。
"""
import re
from typing import Optional

from fastapi import APIRouter, Query

from app.custom.database import get_db as get_db_custom
from app.logs.api_logger import *
from app.service.match_input_tip import match_locations_batch
from common.config import QUERY_DB_ADMIN, QUERY_DB_USER

router = APIRouter()


@router.get("/batch_match")
async def batch_match(
        request: Request,
        input_string: str = Query(..., description="用戶輸入的字符串，用於後端匹配正確的地點"),
        filter_valid_abbrs_only: bool = Query(True, description="是否過濾沒有字表的簡稱（若為真則過濾）"),
        db: Session = Depends(get_db_custom),
        user: Optional[User] = Depends(get_current_user),
):
    """
    用于 /api/batch_match 路由，匹配用戶輸入的地點，並提示正確的地點。
    - input_string-用戶輸入的字符串，用於後端匹配正確的地點
    - filter_valid_abbrs_only-是否過濾沒有字表的簡稱（若為真則過濾）
    - 返回值：
        "success": bool, 代表是否找到完全相同的
        "message": 提示信息
        "items": 所有匹配的地點序列
    """
    # update_count(request.url.path)
    log_all_fields(request.url.path, {
        "input_string": input_string,
        "filter_valid_abbrs_only": filter_valid_abbrs_only
    })
    # start = time.time()
    try:
        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
        input_string = input_string.strip()
        if not input_string:
            return []
        results = match_locations_batch(input_string, filter_valid_abbrs_only, False,
                                        query_db=query_db, db=db, user=user)
        responses = []
        for idx, res in enumerate(results):
            part = re.split(r"[ ,;/，；、]+", input_string)[idx].strip()
            success = bool(res[1])
            if success:
                responses.append({
                    "success": True,
                    "message": f"“{part}”匹配成功",
                    "items": res[0]
                })
            else:
                merged, seen = [], set()
                for i in [0, 3, 5, 7]:
                    val = res[i]
                    if isinstance(val, list):
                        for item in val:
                            if item not in seen:
                                merged.append(item)
                                seen.add(item)
                    elif val not in seen:
                        merged.append(val)
                        seen.add(val)
                responses.append({
                    "success": False,
                    "message": f"第{idx + 1}個“{part}”未匹配",
                    "items": merged
                })
        return responses
    finally:
        print("batch_match")
        # duration = time.time() - start
        # log_detailed_api(
        #     request.url.path, duration, 200,
        #     request.client.host, request.headers.get("user-agent", ""),
        #     request.headers.get("referer", "")
        # )
