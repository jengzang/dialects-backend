import os
import sqlite3
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.sql.db_pool import get_db_pool
from common.path import ADMIN_ONLY_DBS, DB_MAPPING


def get_db_connection(
    db_key: str,
    user: Optional["User"] = None,
    operation: str = "read",
    auth_db: Optional[Session] = None
):
    """
    根据代号获取对应的数据库连接（使用连接池）

    Args:
        db_key: 数据库代号
        user: 当前用户（可选）
        operation: 操作类型（read/write）
        auth_db: auth.db 的数据库会话（用于查询权限）

    Raises:
        HTTPException: 权限不足或数据库不存在
    """
    db_path = DB_MAPPING.get(db_key)

    if not db_path:
        raise HTTPException(status_code=400, detail=f"无效的数据库代号: {db_key}")

    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail=f"数据库文件不存在: {db_path}")

    # 权限检查
    if operation == "read":
        if not _check_read_permission(user, db_key):
            raise HTTPException(status_code=403, detail=f"无权限读取数据库: {db_key}")
    elif operation == "write":
        if not _check_write_permission(auth_db, user, db_key):
            raise HTTPException(status_code=403, detail=f"无权限修改数据库: {db_key}")

    pool = get_db_pool(db_path)
    return pool.get_connection()


def _check_read_permission(user: Optional["User"], db_key: str) -> bool:
    """检查读权限"""
    # 管理员拥有所有权限
    if user and user.role == "admin":
        return True

    # 管理员专属数据库，非管理员不能读
    if db_key in ADMIN_ONLY_DBS:
        return False

    # 公共数据库，所有人可读（包括未登录用户）
    return True


def _check_write_permission(auth_db: Optional[Session], user: Optional["User"], db_key: str) -> bool:
    """检查写权限（带缓存）"""
    # 延迟导入避免循环依赖
    from app.auth.models import UserDbPermission
    from app.auth.permission_cache import get_cached_permission_sync, set_cached_permission_sync

    # 管理员拥有所有权限
    if user and user.role == "admin":
        return True

    # 未登录用户无写权限
    if not user or not auth_db:
        return False

    # 1. 先检查缓存
    cached_permission = get_cached_permission_sync(user.id, db_key)
    if cached_permission is not None:
        return cached_permission

    # 2. 缓存未命中，查询数据库
    permission = auth_db.query(UserDbPermission).filter(
        UserDbPermission.user_id == user.id,
        UserDbPermission.db_key == db_key
    ).first()

    has_permission = permission and permission.can_write

    # 3. 将结果写入缓存
    set_cached_permission_sync(user.id, db_key, has_permission)

    return has_permission
