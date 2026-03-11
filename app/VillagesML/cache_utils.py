"""
VillagesML 缓存工具
Cache utilities for VillagesML APIs
"""
import json
import hashlib
from functools import wraps
from typing import Any, Callable, Optional
from app.redis_client import redis_client


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    生成缓存键
    Generate cache key from function arguments

    Args:
        prefix: 缓存键前缀
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        缓存键字符串
    """
    # 将参数序列化为字符串
    key_parts = [prefix]

    if args:
        key_parts.append(str(args))

    if kwargs:
        # 排序kwargs以确保一致性
        sorted_kwargs = sorted(kwargs.items())
        key_parts.append(str(sorted_kwargs))

    # 生成哈希值以避免键过长
    key_str = ":".join(key_parts)
    key_hash = hashlib.md5(key_str.encode()).hexdigest()

    return f"villagesml:{prefix}:{key_hash}"


def api_cache(ttl: int = 300, prefix: Optional[str] = None):
    """
    API缓存装饰器
    Cache decorator for API endpoints

    Args:
        ttl: 缓存过期时间（秒），默认5分钟
        prefix: 缓存键前缀，默认使用函数名

    Usage:
        @api_cache(ttl=300, prefix="my_api")
        async def my_api_function():
            return {"data": "value"}
    """
    def decorator(func: Callable) -> Callable:
        cache_prefix = prefix or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = generate_cache_key(cache_prefix, *args, **kwargs)

            # 尝试从缓存获取
            try:
                cached_value = await redis_client.get(cache_key)
                if cached_value is not None:
                    # 缓存命中，反序列化并返回
                    return json.loads(cached_value)
            except Exception as e:
                # 缓存读取失败，继续执行函数
                pass

            # 缓存未命中，执行函数
            result = await func(*args, **kwargs)

            # 将结果存入缓存
            try:
                serialized = json.dumps(result, ensure_ascii=False)
                await redis_client.setex(cache_key, ttl, serialized)
            except Exception as e:
                # 缓存写入失败不影响主流程
                pass

            return result

        return wrapper
    return decorator
