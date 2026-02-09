# routes/batch_match.py
"""
[PKG] 路由模塊：處理 /api/batch_match 地點名稱匹配。
"""
import re
from typing import Optional

from fastapi import APIRouter, Query, Request, Depends
from sqlalchemy.orm import Session

from app.custom.database import get_db as get_db_custom
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User
from app.service.match_input_tip import match_locations_batch
from common.path import QUERY_DB_ADMIN, QUERY_DB_USER

router = APIRouter()


@router.get("/batch_match")
async def batch_match(
        request: Request,
        input_string: str = Query(..., description="用戶輸入的字符串，用於後端匹配正確的地點"),
        filter_valid_abbrs_only: bool = Query(True, description="是否過濾沒有字表的簡稱（若為真則過濾）"),
        db: Session = Depends(get_db_custom),
        user: Optional[User] = Depends(ApiLimiter),  # 自动限流和日志记录
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
    # 限流和日志记录已由中间件和依赖注入自动处理
    try:
        # 检查客户端是否已断开连接
        if await request.is_disconnected():
            print(f"[WARN] 客户端已断开连接，跳过处理: {input_string[:50]}")
            return []

        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
        input_string = input_string.strip()
        if not input_string:
            return []
        results = match_locations_batch(input_string, filter_valid_abbrs_only, False,
                                        query_db=query_db, db=db, user=user)
        responses = []
        for idx, res in enumerate(results):
            # 定期检查客户端连接状态
            if idx % 5 == 0 and await request.is_disconnected():
                print(f"[WARN] 处理过程中客户端断开连接，已处理 {idx}/{len(results)} 项")
                break

            part = re.split(r"[ ,;/，；、]+", input_string)[idx].strip()
            success = bool(res[1])
            if success:
                responses.append({
                    "success": True,
                    "message": f"{part}匹配成功",
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
                    "message": f"第{idx + 1}個{part}未匹配",
                    "items": merged
                })
        return responses
    except Exception as e:
        # 捕获并记录异常，避免未处理的错误
        print(f"[ERROR] batch_match 处理异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        print("batch_match")
