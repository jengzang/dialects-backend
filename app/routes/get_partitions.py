# routes/get_partitions.py
"""
[PKG] 路由模塊：處理 /api/partitions 調用分區階層。
"""
from typing import Optional

from fastapi import APIRouter, Query
from app.service.match_input_tip import read_partition_hierarchy
from app.logs.api_logger import *

router = APIRouter()

@router.get("/partitions")
async def api_get_partitions(request: Request, parent: Optional[str] = Query(None)):
    """
    - 獲取下一級的音典分區。
    - 傳入parent-當前分區名（某一級，例如嶺南）；
    - 返回下一級所有的音典分區（partitions子數組），以及層級（level）
    """
    # update_count(request.url.path)
    log_all_fields(request.url.path, {"parent": parent})
    # start = time.time()
    try:
        result = read_partition_hierarchy(parent)
        return result
    finally:
        print("api_get_partitions")
        # duration = time.time() - start
        # log_detailed_api(request.url.path, duration, 200, request.client.host, request.headers.get("user-agent", ""),
        #                  request.headers.get("referer", ""))
