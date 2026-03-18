"""
API 限流依赖注入：自动检查 API 使用限制
"""
from typing import Optional
from fastapi import Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.service.auth.database.connection import get_db
from app.service.auth.core.dependencies import get_current_user, check_api_usage_limit
from app.service.auth.database.models import User
from app.service.logging.utils.route_matcher import match_route_config, should_skip_route
from app.common.config import REQUIRE_LOGIN


async def api_limiter_dependency(
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
) -> Optional[User]:
    """
    API 限流依赖注入

    功能：
    1. 根据配置自动检查 API 使用限制
    2. 支持强制登录检查
    3. 返回用户对象供路由使用

    使用方式：
        @router.post("/api/phonology")
        async def phonology(
            user: Optional[User] = Depends(api_limiter_dependency)
        ):
            # 此时已经完成限流检查
            ...
    """
    path = request.url.path

    # 跳过白名单路由
    if should_skip_route(path):
        return user

    # 获取路由配置
    config = match_route_config(path)

    require_login = config.get("require_login", REQUIRE_LOGIN)
    if require_login and user is None:
        raise HTTPException(status_code=401, detail="[TIP] 请先登录")

    # 如果不需要限流，登录检查后即可返回
    if not config.get("rate_limit"):
        return user

    # 执行限流检查
    ip_address = request.client.host

    user_info = f"用户: {user.username}" if user else "匿名用户"
    # print(f"[ApiLimiter] {user_info}, IP: {ip_address}, 需要登录: {require_login}")

    try:
        await check_api_usage_limit(db, user, require_login, ip_address=ip_address)
        # print(f"[ApiLimiter] ✅ 限流检查通过")
    except HTTPException as e:
        print(f"[ApiLimiter] rate limit check failed: {e.detail}")
        # 限流异常直接抛出
        raise
    except Exception as e:
        print(f"[ERROR] rate limit check failed: {e}")
        # 其他异常不阻塞请求（可根据需求调整）

    return user


# 便捷别名
ApiLimiter = api_limiter_dependency
