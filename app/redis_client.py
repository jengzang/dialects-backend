# redis_client.py
import redis.asyncio as redis  # ✅ 關鍵：導入 asyncio 版本
import os

# 配置 Redis 地址
# 建議：生產環境最好從環境變量讀取，這裡為了方便先寫死
REDIS_HOST = os.getenv("REDIS_HOST", "172.28.199.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# 創建連接池 (Connection Pool)
# 使用連接池是最佳實踐，可以自動管理連接復用
pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,  # ✅ 自動將 bytes 解碼為 string
    socket_timeout=5,       # 設置超時防止卡死
)

# 創建客戶端實例
# 所有的代碼都將引用這個變量
redis_client = redis.Redis(connection_pool=pool)

async def close_redis():
    """關閉 Redis 連接，在應用關閉時調用"""
    await redis_client.close()
    print("🔒 Redis connection closed.")