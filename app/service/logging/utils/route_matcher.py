"""
路由匹配工具：支持精确匹配、前缀匹配、通配符匹配
"""
import fnmatch
from typing import Dict, Any
from app.common.api_config import API_ROUTE_CONFIG, API_DEFAULT_CONFIG, API_WHITELIST, API_BLACKLIST


def match_route_config(path: str) -> Dict[str, Any]:
    """
    根据路径匹配配置

    优先级：
    1. 黑名单（最高优先级）
    2. 白名单
    3. 精确匹配
    4. 通配符匹配
    5. 默认配置
    """
    # 1. 检查黑名单
    for pattern in API_BLACKLIST:
        if fnmatch.fnmatch(path, pattern):
            return {
                "rate_limit": True,
                "require_login": True,
                "log_params": True,
                "log_body": True,
                "is_blacklisted": True,
            }

    # 2. 检查白名单
    for pattern in API_WHITELIST:
        if fnmatch.fnmatch(path, pattern):
            return {
                "rate_limit": False,
                "require_login": False,
                "log_params": False,
                "log_body": False,
                "is_whitelisted": True,
            }

    # 3. 精确匹配
    if path in API_ROUTE_CONFIG:
        return API_ROUTE_CONFIG[path]

    # 4. 通配符匹配（按模式具体度降序，避免 /api/villages/* 抢先匹配 /api/villages/compute/*）
    wildcard_patterns = [
        (pattern, config)
        for pattern, config in API_ROUTE_CONFIG.items()
        if "*" in pattern
    ]
    wildcard_patterns.sort(key=lambda item: len(item[0].replace("*", "")), reverse=True)
    for pattern, config in wildcard_patterns:
        if fnmatch.fnmatch(path, pattern):
            return config

    # 5. 默认配置
    return API_DEFAULT_CONFIG


def should_skip_route(path: str) -> bool:
    """判断是否应该跳过此路由"""
    config = match_route_config(path)
    return config.get("is_whitelisted", False)
