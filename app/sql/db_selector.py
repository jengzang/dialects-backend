"""
数据库选择依赖注入

根据用户角色自动选择合适的数据库路径。
这个模块提供了统一的数据库选择逻辑，避免在每个路由函数中重复判断。

使用方式：
    @router.post("/endpoint")
    async def endpoint(
        dialects_db: str = Depends(get_dialects_db),
        query_db: str = Depends(get_query_db)
    ):
        # 直接使用 dialects_db 和 query_db
        result = some_service(db_path=dialects_db, query_db=query_db)
"""
from typing import Optional
from fastapi import Depends

from app.service.auth.dependencies import get_current_user
from app.service.auth.models import User
from app.common.path import (
    DIALECTS_DB_ADMIN,
    DIALECTS_DB_USER,
    QUERY_DB_ADMIN,
    QUERY_DB_USER
)


def get_dialects_db(user: Optional[User] = Depends(get_current_user)) -> str:
    """
    根据用户角色返回方言数据库路径

    Args:
        user: 当前用户（通过依赖注入自动获取）

    Returns:
        str: 数据库路径
            - 管理员用户: DIALECTS_DB_ADMIN
            - 普通用户/未登录: DIALECTS_DB_USER

    Example:
        @router.post("/phonology")
        async def analyze(
            dialects_db: str = Depends(get_dialects_db)
        ):
            result = query_database(dialects_db)
    """
    return DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER


def get_query_db(user: Optional[User] = Depends(get_current_user)) -> str:
    """
    根据用户角色返回查询数据库路径

    Args:
        user: 当前用户（通过依赖注入自动获取）

    Returns:
        str: 数据库路径
            - 管理员用户: QUERY_DB_ADMIN
            - 普通用户/未登录: QUERY_DB_USER

    Example:
        @router.get("/search")
        async def search(
            query_db: str = Depends(get_query_db)
        ):
            result = search_database(query_db)
    """
    return QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
