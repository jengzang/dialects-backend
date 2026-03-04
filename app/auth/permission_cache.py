"""
用户权限缓存工具

提供基于Redis的用户数据库权限缓存功能
避免每次请求都查询 user_db_permissions 表
"""
from typing import Optional
from app.redis_client import redis_client
import redis


# 缓存配置
PERMISSION_CACHE_TTL = 600  # 权限缓存过期时间（秒），默认10分钟
PERMISSION_CACHE_PREFIX = "permission:"  # 缓存键前缀

# 创建同步Redis客户端（用于同步函数）
try:
    import os
    from app.common.config import _RUN_TYPE

    if _RUN_TYPE == 'WEB':
        REDIS_HOST = os.getenv("REDIS_HOST", "172.28.199.1")
        REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
        REDIS_DB = int(os.getenv("REDIS_DB", 0))

        sync_redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
            socket_timeout=1,  # 短超时，避免阻塞
            socket_connect_timeout=1
        )
    else:
        sync_redis_client = None
except Exception as e:
    print(f"[PermCache] Failed to create sync Redis client: {e}")
    sync_redis_client = None


def generate_permission_cache_key(user_id: int, db_key: str) -> str:
    """
    生成权限缓存键

    Args:
        user_id: 用户ID
        db_key: 数据库代号

    Returns:
        缓存键，格式: permission:{user_id}:{db_key}
    """
    return f"{PERMISSION_CACHE_PREFIX}{user_id}:{db_key}"


def get_cached_permission_sync(user_id: int, db_key: str) -> Optional[bool]:
    """
    从缓存获取用户权限（同步版本）

    Args:
        user_id: 用户ID
        db_key: 数据库代号

    Returns:
        True: 有写权限
        False: 无写权限
        None: 缓存未命中或Redis不可用
    """
    if not sync_redis_client:
        return None

    try:
        cache_key = generate_permission_cache_key(user_id, db_key)
        cached_value = sync_redis_client.get(cache_key)

        if cached_value is None:
            return None

        # 将字符串转换为布尔值
        return cached_value.lower() == "true"
    except Exception as e:
        # 缓存失败不影响主流程
        # print(f"[PermCache] Get error: {e}")
        return None


def set_cached_permission_sync(user_id: int, db_key: str, can_write: bool, ttl: int = PERMISSION_CACHE_TTL):
    """
    设置用户权限缓存（同步版本）

    Args:
        user_id: 用户ID
        db_key: 数据库代号
        can_write: 是否有写权限
        ttl: 过期时间（秒）
    """
    if not sync_redis_client:
        return

    try:
        cache_key = generate_permission_cache_key(user_id, db_key)
        # 将布尔值转换为字符串存储
        sync_redis_client.setex(cache_key, ttl, str(can_write))
    except Exception as e:
        # 缓存失败不影响主流程
        # print(f"[PermCache] Set error: {e}")
        pass


def invalidate_user_permission_sync(user_id: int, db_key: Optional[str] = None):
    """
    清除用户权限缓存（同步版本）

    当用户权限被修改时调用此函数

    Args:
        user_id: 用户ID
        db_key: 数据库代号，如果为None则清除该用户的所有权限缓存
    """
    if not sync_redis_client:
        return

    try:
        if db_key:
            # 清除特定数据库的权限缓存
            cache_key = generate_permission_cache_key(user_id, db_key)
            sync_redis_client.delete(cache_key)
            print(f"[PermCache] Invalidated permission for user {user_id}, db {db_key}")
        else:
            # 清除该用户的所有权限缓存
            pattern = f"{PERMISSION_CACHE_PREFIX}{user_id}:*"
            deleted_count = 0

            for key in sync_redis_client.scan_iter(match=pattern, count=100):
                sync_redis_client.delete(key)
                deleted_count += 1

            if deleted_count > 0:
                print(f"[PermCache] Invalidated {deleted_count} permissions for user {user_id}")
    except Exception as e:
        print(f"[PermCache] Invalidate error: {e}")


# 异步版本（用于异步上下文）
async def get_cached_permission(user_id: int, db_key: str) -> Optional[bool]:
    """
    从缓存获取用户权限（异步版本）

    Args:
        user_id: 用户ID
        db_key: 数据库代号

    Returns:
        True: 有写权限
        False: 无写权限
        None: 缓存未命中
    """
    try:
        cache_key = generate_permission_cache_key(user_id, db_key)
        cached_value = await redis_client.get(cache_key)

        if cached_value is None:
            return None

        # 将字符串转换为布尔值
        return cached_value.lower() == "true"
    except Exception as e:
        # 缓存失败不影响主流程
        # print(f"[PermCache] Get error: {e}")
        return None


async def set_cached_permission(user_id: int, db_key: str, can_write: bool, ttl: int = PERMISSION_CACHE_TTL):
    """
    设置用户权限缓存（异步版本）

    Args:
        user_id: 用户ID
        db_key: 数据库代号
        can_write: 是否有写权限
        ttl: 过期时间（秒）
    """
    try:
        cache_key = generate_permission_cache_key(user_id, db_key)
        # 将布尔值转换为字符串存储
        await redis_client.setex(cache_key, ttl, str(can_write))
    except Exception as e:
        # 缓存失败不影响主流程
        # print(f"[PermCache] Set error: {e}")
        pass


async def invalidate_user_permission(user_id: int, db_key: Optional[str] = None):
    """
    清除用户权限缓存（异步版本）

    当用户权限被修改时调用此函数

    Args:
        user_id: 用户ID
        db_key: 数据库代号，如果为None则清除该用户的所有权限缓存
    """
    try:
        if db_key:
            # 清除特定数据库的权限缓存
            cache_key = generate_permission_cache_key(user_id, db_key)
            await redis_client.delete(cache_key)
            print(f"[PermCache] Invalidated permission for user {user_id}, db {db_key}")
        else:
            # 清除该用户的所有权限缓存
            pattern = f"{PERMISSION_CACHE_PREFIX}{user_id}:*"
            deleted_count = 0

            async for key in redis_client.scan_iter(match=pattern, count=100):
                await redis_client.delete(key)
                deleted_count += 1

            if deleted_count > 0:
                print(f"[PermCache] Invalidated {deleted_count} permissions for user {user_id}")
    except Exception as e:
        print(f"[PermCache] Invalidate error: {e}")


async def clear_all_permission_cache():
    """
    清除所有权限缓存（异步版本）

    用于调试或维护
    """
    try:
        pattern = f"{PERMISSION_CACHE_PREFIX}*"
        deleted_count = 0

        async for key in redis_client.scan_iter(match=pattern, count=100):
            await redis_client.delete(key)
            deleted_count += 1

        print(f"[PermCache] Cleared {deleted_count} permission cache entries")
        return deleted_count
    except Exception as e:
        print(f"[PermCache] Clear error: {e}")
        return 0
