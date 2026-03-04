"""
管理缓存的API端点（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化

业务逻辑在 app.admin.cache_service 中实现
"""
from fastapi import APIRouter
from app.admin import cache_service

router = APIRouter()


@router.post("/clear_dialect_cache")
async def clear_dialect_cache_endpoint(db_path: str = None):
    """
    清除方言数据缓存（仅管理员可用）

    Args:
        db_path: 指定数据库路径，如果为None则清除所有缓存

    Returns:
        清除结果
    """
    return cache_service.clear_dialect_cache_logic(db_path)


@router.post("/clear_redis_cache")
async def clear_redis_cache_endpoint(pattern: str = "*"):
    """
    清除Redis缓存（仅管理员可用）

    Args:
        pattern: 匹配模式，默认为 "*"（所有键）

    Returns:
        清除结果
    """
    return await cache_service.clear_redis_cache_logic(pattern)


@router.post("/clear_all_cache")
async def clear_all_cache_endpoint():
    """
    清除所有缓存（仅管理员可用）

    Returns:
        清除结果
    """
    return await cache_service.clear_all_cache_logic()


@router.get("/cache_stats")
async def cache_stats_endpoint():
    """
    查看所有缓存统计信息（仅管理员可用）

    Returns:
        缓存统计信息（数量、内存占用）
    """
    return await cache_service.get_cache_stats()


@router.get("/cache_status")
async def cache_status_endpoint():
    """
    查看缓存状态（仅管理员可用）- 简化版本

    Returns:
        缓存统计信息
    """
    return cache_service.get_cache_status()
