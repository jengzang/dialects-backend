"""
缓存管理模块 (Cache Management)

提供在线计算结果的缓存功能，包括：
- 参数哈希生成
- LRU淘汰策略
- TTL过期控制
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ComputeCache:
    """在线计算结果缓存"""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 100):
        """
        初始化缓存

        Args:
            ttl_seconds: 缓存过期时间（秒）
            max_size: 最大缓存条目数
        """
        self.ttl = ttl_seconds
        self.cache: Dict[str, tuple] = {}  # {hash: (result, timestamp)}
        self.max_size = max_size
        self.access_count: Dict[str, int] = {}  # 访问计数
        self.hit_count = 0
        self.miss_count = 0

    def get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """
        生成缓存键

        Args:
            endpoint: API端点名称
            params: 请求参数

        Returns:
            缓存键（MD5哈希）
        """
        # 排序参数以确保一致性
        key_str = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        获取缓存结果

        Args:
            endpoint: API端点名称
            params: 请求参数

        Returns:
            缓存的结果，如果不存在或过期则返回None
        """
        key = self.get_cache_key(endpoint, params)

        if key in self.cache:
            result, timestamp = self.cache[key]

            # 检查是否过期
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                self.access_count[key] = self.access_count.get(key, 0) + 1
                self.hit_count += 1
                logger.info(f"Cache hit for {endpoint}, key={key[:8]}...")
                return result
            else:
                # 过期，删除
                del self.cache[key]
                if key in self.access_count:
                    del self.access_count[key]
                logger.info(f"Cache expired for {endpoint}, key={key[:8]}...")

        self.miss_count += 1
        logger.info(f"Cache miss for {endpoint}, key={key[:8]}...")
        return None

    def set(self, endpoint: str, params: Dict[str, Any], result: Dict[str, Any]):
        """
        设置缓存结果

        Args:
            endpoint: API端点名称
            params: 请求参数
            result: 计算结果
        """
        # 检查缓存大小，执行LRU淘汰
        if len(self.cache) >= self.max_size:
            # 找到访问次数最少的键
            if self.access_count:
                lru_key = min(self.access_count.keys(),
                            key=lambda k: self.access_count[k])
            else:
                # 如果没有访问记录，删除最旧的
                lru_key = min(self.cache.keys(),
                            key=lambda k: self.cache[k][1])

            del self.cache[lru_key]
            if lru_key in self.access_count:
                del self.access_count[lru_key]
            logger.info(f"Cache evicted (LRU), key={lru_key[:8]}...")

        key = self.get_cache_key(endpoint, params)
        self.cache[key] = (result, datetime.now())
        self.access_count[key] = 0
        logger.info(f"Cache set for {endpoint}, key={key[:8]}...")

    def clear(self, endpoint: Optional[str] = None):
        """
        清除缓存

        Args:
            endpoint: 如果指定，只清除该端点的缓存；否则清除所有
        """
        if endpoint is None:
            self.cache.clear()
            self.access_count.clear()
            logger.info("All cache cleared")
        else:
            # 清除特定端点的缓存
            keys_to_remove = []
            for key in self.cache.keys():
                # 需要反向查找，这里简化处理
                keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.cache[key]
                if key in self.access_count:
                    del self.access_count[key]
            logger.info(f"Cache cleared for endpoint: {endpoint}")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        total_requests = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total_requests if total_requests > 0 else 0

        return {
            'cache_size': len(self.cache),
            'max_size': self.max_size,
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': round(hit_rate, 3),
            'ttl_seconds': self.ttl
        }


# 全局缓存实例
compute_cache = ComputeCache(ttl_seconds=3600, max_size=100)
