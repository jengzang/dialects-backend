# routes/get_partitions.py
"""
[PKG] 路由模塊：處理 /api/partitions 調用分區階層。
"""
from typing import Optional

from fastapi import APIRouter, Query, Depends
from app.service.match_input_tip import read_partition_hierarchy
from app.logs.service.api_limiter import ApiLimiter
from app.auth.models import User

router = APIRouter()

@router.get("/partitions")
async def api_get_partitions(
        parent: Optional[str] = Query(None),
        user: Optional[User] = Depends(ApiLimiter)  # 自动限流和日志记录
):
    """
    - 獲取下一級的音典分區。
    - 傳入parent-當前分區名（某一級，例如嶺南）；
    - 返回下一級所有的音典分區（partitions子數組），以及層級（level）
    """
    # 限流和日志记录已由中间件和依赖注入自动处理
    try:
        result = read_partition_hierarchy(parent)
        return result
    finally:
        print("api_get_partitions")
