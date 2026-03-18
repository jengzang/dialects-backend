"""
In-memory cache for villagesML compute endpoints.
"""

import copy
import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ComputeCache:
    """Simple TTL + LRU-ish in-memory cache."""

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 100):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self.cache: Dict[str, tuple[Dict[str, Any], datetime]] = {}
        self.access_count: Dict[str, int] = {}
        self.hit_count = 0
        self.miss_count = 0
        self._lock = threading.RLock()

    def get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        key_str = f"{endpoint}:{json.dumps(params, sort_keys=True, ensure_ascii=False)}"
        digest = hashlib.md5(key_str.encode("utf-8")).hexdigest()
        return f"{endpoint}:{digest}"

    def get(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = self.get_cache_key(endpoint, params)
        with self._lock:
            if key in self.cache:
                result, timestamp = self.cache[key]
                if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                    self.access_count[key] = self.access_count.get(key, 0) + 1
                    self.hit_count += 1
                    logger.info("Cache hit for %s, key=%s...", endpoint, key[:8])
                    return copy.deepcopy(result)

                # expired
                del self.cache[key]
                self.access_count.pop(key, None)
                logger.info("Cache expired for %s, key=%s...", endpoint, key[:8])

            self.miss_count += 1
            logger.info("Cache miss for %s, key=%s...", endpoint, key[:8])
            return None

    def set(self, endpoint: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        key = self.get_cache_key(endpoint, params)
        with self._lock:
            if len(self.cache) >= self.max_size:
                if self.access_count:
                    lru_key = min(self.access_count.keys(), key=lambda k: self.access_count[k])
                else:
                    lru_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
                self.cache.pop(lru_key, None)
                self.access_count.pop(lru_key, None)
                logger.info("Cache evicted (LRU), key=%s...", lru_key[:8])

            self.cache[key] = (copy.deepcopy(result), datetime.now())
            self.access_count[key] = 0
            logger.info("Cache set for %s, key=%s...", endpoint, key[:8])

    def clear(self, endpoint: Optional[str] = None) -> None:
        with self._lock:
            if endpoint is None:
                self.cache.clear()
                self.access_count.clear()
                logger.info("All cache cleared")
                return

            keys_to_remove = [
                key for key in list(self.cache.keys())
                if key.split(":", 1)[0].startswith(endpoint)
            ]
            for key in keys_to_remove:
                self.cache.pop(key, None)
                self.access_count.pop(key, None)
            logger.info("Cache cleared for endpoint: %s", endpoint)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_requests = self.hit_count + self.miss_count
            hit_rate = self.hit_count / total_requests if total_requests > 0 else 0.0
            return {
                "cache_size": len(self.cache),
                "max_size": self.max_size,
                "hit_count": self.hit_count,
                "miss_count": self.miss_count,
                "hit_rate": round(hit_rate, 3),
                "ttl_seconds": self.ttl,
            }


compute_cache = ComputeCache(ttl_seconds=3600, max_size=100)

