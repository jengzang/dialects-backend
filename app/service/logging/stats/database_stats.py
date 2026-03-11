"""
数据库统计业务逻辑

提供数据库大小、表统计等功能的纯业务逻辑实现
"""

import os
from typing import Dict, Any

from app.common.path import LOGS_DATABASE_PATH


def get_database_size() -> Dict[str, Any]:
    """
    获取数据库文件大小

    Returns:
        数据库大小信息（字节和MB）
    """
    if not os.path.exists(LOGS_DATABASE_PATH):
        return {
            "path": LOGS_DATABASE_PATH,
            "exists": False,
            "size_bytes": 0,
            "size_mb": 0
        }

    size_bytes = os.path.getsize(LOGS_DATABASE_PATH)
    size_mb = round(size_bytes / (1024 * 1024), 2)

    return {
        "path": LOGS_DATABASE_PATH,
        "exists": True,
        "size_bytes": size_bytes,
        "size_mb": size_mb
    }
