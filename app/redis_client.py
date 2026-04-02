# redis_client.py
import os
from app.common.config import _RUN_TYPE

# ============ 空的 Redis 模拟类（用于非 WEB 模式） ============
class DummyRedis:
    """空的 Redis 实现，所有操作都不做任何事"""

    async def get(self, key):
        """模拟 get 操作，总是返回 None（缓存未命中）"""
        return None

    async def set(self, key, value, ex=None):
        """模拟 set 操作，什么都不做"""
        pass

    async def setex(self, key, time, value):
        """模拟 setex 操作，什么都不做"""
        pass

    async def close(self):
        """模拟 close 操作，什么都不做"""
        pass


class DummySyncRedis:
    """同步版本的空 Redis 实现"""

    def get(self, key):
        """模拟 get 操作，总是返回 None（缓存未命中）"""
        return None

    def set(self, key, value, ex=None):
        """模拟 set 操作，什么都不做"""
        pass

    def setex(self, key, time, value):
        """模拟 setex 操作，什么都不做"""
        pass

    def delete(self, key):
        """模拟 delete 操作，什么都不做"""
        pass

    def incr(self, key):
        """模拟 incr 操作，返回允许通过的初始计数。"""
        return 1

    def expire(self, key, time):
        """模拟 expire 操作，什么都不做"""
        pass


# ============ 根据运行模式创建 Redis 客户端 ============
if _RUN_TYPE == 'WEB':
    # WEB 模式：使用真实的 Redis
    import redis.asyncio as redis
    import redis as sync_redis

    REDIS_HOST = os.getenv("REDIS_HOST", "172.28.199.1")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))

    # 异步 Redis 客户端
    pool = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_timeout=5,
    )
    redis_client = redis.Redis(connection_pool=pool)

    # 同步 Redis 客户端
    sync_redis_client = sync_redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5
    )

    print(f"[OK] Redis 已启用 (WEB 模式)")

else:
    # MINE/EXE 模式：使用空实现
    redis_client = DummyRedis()
    sync_redis_client = DummySyncRedis()
    print(f"[!] Redis 已禁用 ({_RUN_TYPE} 模式)")


async def close_redis():
    """关闭 Redis 连接，在应用关闭时调用"""
    if _RUN_TYPE == 'WEB':
        await redis_client.close()
        if hasattr(sync_redis_client, 'close'):
            sync_redis_client.close()
        print("[CLOSE] Redis connection closed.")
    else:
        print(f"[!] Redis 未启用，无需关闭 ({_RUN_TYPE} 模式)")
