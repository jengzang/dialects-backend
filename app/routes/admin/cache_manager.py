"""
管理缓存的API端点
"""
import sys
from fastapi import APIRouter
from app.service.match_input_tip import clear_dialect_cache, _dialect_cache
from app.redis_client import redis_client
from common.config import _RUN_TYPE
from common.path import QUERY_DB_ADMIN, QUERY_DB_USER

router = APIRouter()


def get_size_mb(obj):
    """递归计算对象占用的内存大小（MB）"""
    size = sys.getsizeof(obj)

    if isinstance(obj, dict):
        size += sum(get_size_mb(k) + get_size_mb(v) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set)):
        size += sum(get_size_mb(item) for item in obj)

    return size / (1024 * 1024)  # 转换为 MB


@router.post("/clear_dialect_cache")
async def clear_dialect_cache_endpoint(
    db_path: str = None,

):
    """
    清除方言数据缓存（仅管理员可用）

    Args:
        db_path: 指定数据库路径，如果为None则清除所有缓存

    Returns:
        清除结果
    """
    try:
        clear_dialect_cache(db_path)
        return {
            "success": True,
            "message": f"方言数据缓存已清除: {db_path if db_path else '所有数据库'}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"清除缓存失败: {str(e)}"
        }


@router.post("/clear_redis_cache")
async def clear_redis_cache_endpoint(
    pattern: str = "*",
):
    """
    清除Redis缓存（仅管理员可用）

    Args:
        pattern: 匹配模式，默认为 "*"（所有键）

    Returns:
        清除结果
    """
    try:
        if _RUN_TYPE != 'WEB':
            return {
                "success": False,
                "message": f"Redis未启用（{_RUN_TYPE}模式）"
            }

        # 获取匹配的键
        keys = []
        async for key in redis_client.scan_iter(match=pattern):
            keys.append(key)

        # 删除键
        if keys:
            deleted = await redis_client.delete(*keys)
        else:
            deleted = 0

        return {
            "success": True,
            "message": f"Redis缓存已清除: {deleted} 个键",
            "deleted_count": deleted
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"清除Redis缓存失败: {str(e)}"
        }


@router.post("/clear_all_cache")
async def clear_all_cache_endpoint(

):
    """
    清除所有缓存（仅管理员可用）

    Returns:
        清除结果
    """
    results = []

    # 清除方言数据缓存
    try:
        clear_dialect_cache()
        results.append({"type": "dialect_cache", "success": True, "message": "方言数据缓存已清除"})
    except Exception as e:
        results.append({"type": "dialect_cache", "success": False, "message": str(e)})

    # 清除Redis缓存
    try:
        if _RUN_TYPE == 'WEB':
            keys = []
            async for key in redis_client.scan_iter(match="*"):
                keys.append(key)
            if keys:
                deleted = await redis_client.delete(*keys)
            else:
                deleted = 0
            results.append({"type": "redis_cache", "success": True, "message": f"Redis缓存已清除: {deleted} 个键"})
        else:
            results.append({"type": "redis_cache", "success": True, "message": f"Redis未启用（{_RUN_TYPE}模式）"})
    except Exception as e:
        results.append({"type": "redis_cache", "success": False, "message": str(e)})

    return {
        "success": True,
        "message": "所有缓存清除完成",
        "results": results
    }


@router.get("/cache_stats")
async def cache_stats_endpoint(

):
    """
    查看所有缓存统计信息（仅管理员可用）

    Returns:
        缓存统计信息（数量、内存占用）
    """
    try:
        stats = {
            "dialect_cache": {},
            "redis_cache": {},
            "total_memory_mb": 0
        }

        # 方言数据缓存统计
        dialect_memory = 0
        for db_path in _dialect_cache['valid_abbrs']:
            stats["dialect_cache"][db_path] = {}
            for filter_flag in _dialect_cache['valid_abbrs'][db_path]:
                abbrs_set = _dialect_cache['valid_abbrs'][db_path][filter_flag]
                geo_list = _dialect_cache['geo_data'][db_path][filter_flag]
                last_update = _dialect_cache['last_update'].get(db_path, 0)

                # 计算内存占用
                abbrs_memory = get_size_mb(abbrs_set)
                geo_memory = get_size_mb(geo_list)
                total_memory = abbrs_memory + geo_memory

                dialect_memory += total_memory

                stats["dialect_cache"][db_path][f"filter_{filter_flag}"] = {
                    "abbrs_count": len(abbrs_set),
                    "geo_data_count": len(geo_list),
                    "memory_mb": round(total_memory, 2),
                    "last_update": last_update
                }

        stats["dialect_cache"]["total_memory_mb"] = round(dialect_memory, 2)
        stats["dialect_cache"]["total_databases"] = len(_dialect_cache['valid_abbrs'])

        # Redis缓存统计
        if _RUN_TYPE == 'WEB':
            try:
                # 获取Redis信息
                info = await redis_client.info('memory')
                used_memory_mb = info.get('used_memory', 0) / (1024 * 1024)

                # 统计键数量
                key_count = 0
                async for _ in redis_client.scan_iter(match="*"):
                    key_count += 1

                stats["redis_cache"] = {
                    "enabled": True,
                    "key_count": key_count,
                    "used_memory_mb": round(used_memory_mb, 2)
                }
            except Exception as e:
                stats["redis_cache"] = {
                    "enabled": True,
                    "error": str(e)
                }
        else:
            stats["redis_cache"] = {
                "enabled": False,
                "message": f"Redis未启用（{_RUN_TYPE}模式）"
            }

        # 计算总内存
        stats["total_memory_mb"] = round(dialect_memory, 2)

        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取缓存统计失败: {str(e)}"
        }


@router.get("/cache_status")
async def cache_status_endpoint(

):
    """
    查看缓存状态（仅管理员可用）- 简化版本

    Returns:
        缓存统计信息
    """
    try:
        status = {}

        for db_path in _dialect_cache['valid_abbrs']:
            status[db_path] = {}
            for filter_flag in _dialect_cache['valid_abbrs'][db_path]:
                abbrs_count = len(_dialect_cache['valid_abbrs'][db_path][filter_flag])
                geo_count = len(_dialect_cache['geo_data'][db_path][filter_flag])
                last_update = _dialect_cache['last_update'].get(db_path, 0)

                status[db_path][f"filter_{filter_flag}"] = {
                    "abbrs_count": abbrs_count,
                    "geo_data_count": geo_count,
                    "last_update": last_update
                }

        return {
            "success": True,
            "cache_status": status,
            "total_databases": len(_dialect_cache['valid_abbrs'])
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取缓存状态失败: {str(e)}"
        }
