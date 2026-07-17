import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from jose import JWTError
from sqlalchemy.orm import Session
from app.service.auth.database import models
from app.service.auth.core import utils
from app.service.auth.database.connection import get_db
from app.service.auth.database.models import User, ApiUsageLog
from app.service.auth.session.service import get_valid_session_by_public_id
from app.service.auth.security.cache_security import sign_user_data, verify_user_data  # ✅ 导入签名函数
from app.common.config import MAX_LOGIN_PER_MINUTE, CACHE_EXPIRATION_TIME
from app.common.auth_config import (
    AUTH_COOKIE_NAME,
    CSRF_ENABLED,
    ALLOWED_ORIGINS,
)
from app.common.api_config import MAX_USER_REQUESTS_PER_HOUR, MAX_IP_REQUESTS_PER_HOUR
from app.redis_client import redis_client


logger = logging.getLogger(__name__)
RATE_LIMIT_DEBUG = os.getenv("RATE_LIMIT_DEBUG", "true").lower() in {"1", "true", "yes", "on"}
_LEGACY_SESSIONLESS_TOKEN_WARNINGS: set[tuple[str, str]] = set()


def user_to_dict(user: models.User) -> dict:
    user_dict = {column.name: getattr(user, column.name) for column in user.__table__.columns}

    # 将 datetime 类型字段转换为字符串
    for key, value in user_dict.items():
        if isinstance(value, datetime):
            user_dict[key] = value.isoformat()  # 转换为 ISO 8601 字符串格式
    return user_dict


def _make_rate_limit_member(now: int) -> str:
    """为滑动窗口计数生成真正唯一的 member，避免同秒覆盖。"""
    return f"{now}:{uuid4().hex}"


def rate_limit_debug(event: str, **fields) -> None:
    """Print rate-limit debug logs only when RATE_LIMIT_DEBUG is enabled."""
    if not RATE_LIMIT_DEBUG:
        return

    parts = [f"event={event}"]
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    print("[RATE_LIMIT]", " ".join(parts))


def warn_legacy_token_without_session(*, username: Optional[str], source: str) -> None:
    """
    Warn once per process when compatibility code accepts a legacy token that
    cannot participate in per-session revocation.
    """
    warning_key = (source, username or "<unknown>")
    if warning_key in _LEGACY_SESSIONLESS_TOKEN_WARNINGS:
        return

    _LEGACY_SESSIONLESS_TOKEN_WARNINGS.add(warning_key)
    logger.warning(
        "Accepted legacy access token without session_id in %s for compatibility; "
        "per-session logout will only take effect after token expiry (user=%s)",
        source,
        username or "<unknown>",
    )


def _format_reset_at(unix_ts: int) -> str:
    """Format a Unix timestamp as an ISO 8601 UTC string."""
    return datetime.utcfromtimestamp(unix_ts).isoformat() + "Z"


def _build_rate_limit_detail(
    *,
    limit_type: str,
    scope: str,
    message: str,
    limit: int,
    current_count: int,
    window_seconds: int,
    retry_after_seconds: Optional[int],
    suggest_login: bool = False,
) -> dict:
    reset_at = None
    if retry_after_seconds is not None:
        reset_at = _format_reset_at(int(utils.now_utc_naive().timestamp()) + retry_after_seconds)

    return {
        "code": "rate_limit_exceeded",
        "limit_type": limit_type,
        "scope": scope,
        "window_type": "sliding_window",
        "window_seconds": window_seconds,
        "limit": limit,
        "current_count": current_count,
        "retry_after_seconds": retry_after_seconds,
        "reset_at": reset_at,
        "suggest_login": suggest_login,
        "message": message,
    }


async def _get_redis_retry_after_seconds(
    key: str,
    *,
    count: int,
    limit: int,
    window_seconds: int,
    now: int,
) -> Optional[int]:
    """
    Estimate when a Redis sliding-window limiter will drop back to <= limit.

    Rejected requests are already inserted into the sorted set before the check,
    so `count` includes the current rejected request.
    """
    overflow = count - limit
    if overflow <= 0:
        overflow = 1

    rows = await redis_client.zrange(key, 0, overflow - 1, withscores=True)
    if not rows:
        return None

    _, score = rows[-1]
    retry_after_seconds = max(1, int(score) + window_seconds - now)
    return retry_after_seconds


async def _raise_redis_rate_limit(
    *,
    key: str,
    count: int,
    limit: int,
    window_seconds: int,
    now: int,
    limit_type: str,
    scope: str,
    message: str,
    suggest_login: bool = False,
) -> None:
    retry_after_seconds = await _get_redis_retry_after_seconds(
        key,
        count=count,
        limit=limit,
        window_seconds=window_seconds,
        now=now,
    )
    detail = _build_rate_limit_detail(
        limit_type=limit_type,
        scope=scope,
        message=message,
        limit=limit,
        current_count=count,
        window_seconds=window_seconds,
        retry_after_seconds=retry_after_seconds,
        suggest_login=suggest_login,
    )
    rate_limit_debug(
        "raise_429",
        key=key,
        limit_type=limit_type,
        scope=scope,
        count=count,
        limit=limit,
        retry_after_seconds=retry_after_seconds,
    )
    headers = {"Retry-After": str(retry_after_seconds)} if retry_after_seconds is not None else None
    raise HTTPException(status_code=429, detail=detail, headers=headers)


async def _rollback_rate_limit_member(key: Optional[str], member: Optional[str]) -> None:
    """Best-effort rollback for a rejected rate-limit record."""
    if not key or not member:
        return

    try:
        await redis_client.zrem(key, member)
        rate_limit_debug("rollback", key=key, member=member)
    except Exception as e:
        print(f"[WARN] Redis 限流回滚失败 ({key}): {e}")


def _raise_login_rate_limit(
    db: Session,
    *,
    ip: str,
    login_attempts: int,
) -> None:
    retry_after_seconds = _get_login_retry_after_seconds(
        db,
        ip=ip,
        login_attempts=login_attempts,
    )
    detail = _build_rate_limit_detail(
        limit_type="login_ip_limit",
        scope="ip",
        message="登录过于频繁，请稍候再试",
        limit=MAX_LOGIN_PER_MINUTE,
        current_count=login_attempts,
        window_seconds=60,
        retry_after_seconds=retry_after_seconds,
        suggest_login=False,
    )
    headers = {"Retry-After": str(retry_after_seconds)} if retry_after_seconds is not None else None
    raise HTTPException(status_code=429, detail=detail, headers=headers)


def _has_active_token_session(db: Session, payload: dict) -> bool:
    session_public_id = payload.get("session_id")
    if not session_public_id:
        return True

    return get_valid_session_by_public_id(db, session_public_id) is not None


def _extract_auth_token(request: Request) -> tuple[Optional[str], Optional[str]]:
    """
    从请求中提取认证 token，同时支持 Authorization Bearer 和 HttpOnly Cookie。

    优先级：Authorization Bearer > Cookie。
    如果 Authorization 头存在，则独占使用（无效也不回退到 Cookie），避免凭证混淆。

    Returns:
        (token, source) — source 为 "bearer" 或 "cookie"；无有效凭证时返回 (None, None)
    """
    auth_header = request.headers.get("Authorization")
    if auth_header:
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):].strip()
            if token:
                return (token, "bearer")
        # Authorization 头存在但格式无效 → 不回退到 Cookie
        return (None, "bearer")

    # 无 Authorization 头 → 读取 Cookie（Web 浏览器）
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        return (token, "cookie")

    return (None, None)


def _validate_csrf(request: Request, auth_source: str) -> None:
    """
    Cookie 认证的写请求需要校验 Origin 头（CSRF 防护）。

    Bearer 认证的请求不需要 CSRF 校验（浏览器不会自动携带 Authorization 头）。
    """
    if not CSRF_ENABLED:
        return
    if auth_source != "cookie":
        return
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return

    origin = request.headers.get("Origin")
    if not origin:
        raise HTTPException(status_code=403, detail="CSRF: Missing Origin header for cookie-based request")

    if origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="CSRF: Untrusted origin")


async def _load_user_from_cache_or_db(db: Session, sub: str, ver: int = 1) -> Optional[models.User]:
    # 新版 token（ver >= 2）：sub 是 user_id，缓存 key 用 user:id:{user_id}
    if ver >= 2:
        user_id = int(sub)
        cache_key = f"user:id:{user_id}"
        cached_user = await redis_client.get(cache_key)
        if cached_user:
            user_dict = verify_user_data(cached_user)
            if user_dict:
                return models.User(**user_dict)
            await redis_client.delete(cache_key)

        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return None

        try:
            signed_data = sign_user_data(user_to_dict(user))
            await redis_client.setex(cache_key, CACHE_EXPIRATION_TIME, signed_data)
        except Exception as e:
            print(f"[X] Failed to update user cache: {e}")
        return user

    # 旧版 token（无 ver 字段，默认为 1）：sub 是 username，保持旧逻辑
    username = sub
    cached_user = await redis_client.get(f"user:{username}")
    if cached_user:
        user_dict = verify_user_data(cached_user)
        if user_dict:
            return models.User(**user_dict)
        await redis_client.delete(f"user:{username}")

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return None

    try:
        signed_data = sign_user_data(user_to_dict(user))
        await redis_client.setex(
            f"user:{username}",
            CACHE_EXPIRATION_TIME,
            signed_data,
        )
    except Exception as e:
        print(f"[X] Failed to update user cache: {e}")

    return user


async def get_current_user(
        request: Request,
        db: Session = Depends(get_db),
        require_admin: bool = False
) -> models.User:
    token, source = _extract_auth_token(request)
    if not token:
        if not require_admin:
            return None
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = utils.decode_access_token(token)
        sub = payload.get("sub")
        ver = payload.get("ver", 1)  # 无 ver 字段的旧 token 默认为 1（sub 是 username）
        if not sub:
            if not require_admin:
                return None
            raise HTTPException(status_code=401, detail="Invalid token")
        if not payload.get("session_id"):
            warn_legacy_token_without_session(
                username=(sub if ver < 2 else None),
                source="get_current_user",
            )
        if not _has_active_token_session(db, payload):
            if not require_admin:
                return None
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        if not require_admin:
            return None
        raise HTTPException(status_code=401, detail="Invalid token")

    # Cookie 认证的写请求需要校验 Origin（CSRF 防护）
    _validate_csrf(request, source)

    user = await _load_user_from_cache_or_db(db, sub, ver)
    if not user:
        return None

    if require_admin and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    return user


async def get_current_user_for_middleware(request: Request, db: Session):
    token, source = _extract_auth_token(request)
    if not token:
        return None

    try:
        payload = utils.decode_access_token(token)
        sub = payload.get("sub")
        ver = payload.get("ver", 1)  # 无 ver 字段的旧 token 默认为 1（sub 是 username）
        if not sub:
            return None
        if not payload.get("session_id"):
            warn_legacy_token_without_session(
                username=(sub if ver < 2 else None),
                source="get_current_user_for_middleware",
            )
        if not _has_active_token_session(db, payload):
            return None
    except JWTError as e:
        print(f"JWT decode error: {e}")
        return None

    # middleware 不需要 CSRF 校验（日志记录用途）
    return await _load_user_from_cache_or_db(db, sub, ver)


async def get_current_admin_user(
    request: Request,
    db: Session = Depends(get_db)
) -> models.User:
    token, source = _extract_auth_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = utils.decode_access_token(token)
        sub = payload.get("sub")
        ver = payload.get("ver", 1)  # 无 ver 字段的旧 token 默认为 1（sub 是 username）
        role_in_jwt = payload.get("role")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not payload.get("session_id"):
        warn_legacy_token_without_session(
            username=(sub if ver < 2 else None),
            source="get_current_admin_user",
        )
    if not _has_active_token_session(db, payload):
        raise HTTPException(status_code=401, detail="Session is no longer active")

    # Cookie 认证的写请求需要校验 Origin（CSRF 防护，admin 操作更严格要求）
    _validate_csrf(request, source)

    user = await _load_user_from_cache_or_db(db, sub, ver)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if role_in_jwt and role_in_jwt != user.role:
        logger.warning(f"[SECURITY] Role mismatch for user_id={user.id}: JWT={role_in_jwt}, DB={user.role}")

    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return user


async def check_api_usage_limit(
        db: Session,
        user: Optional[User],
        require_login: bool = False,
        ip_address: Optional[str] = None,
        path: Optional[str] = None
) -> None:
    """
    API 限流檢查（滑動窗口 + 雙重計數）

    策略：
    - 所有請求都記錄 IP 計數（無論是否登錄）
    - 已登錄用戶額外記錄用戶計數
    - 兩個計數器獨立觸發限流，取更嚴格的那個
    - 防止用戶達到用戶限額後退出登錄繞過限制

    限額：
    - 管理員：不限流
    - 已登錄用戶：IP 計數 ≤ MAX_USER_REQUESTS_PER_HOUR，用戶計數 ≤ MAX_USER_REQUESTS_PER_HOUR（任一達到即限流）
    - 未登錄遊客：IP 計數 ≤ MAX_IP_REQUESTS_PER_HOUR
    """
    import time

    # 1) 管理員不受限制
    if user and user.role == "admin":
        return

    # 2) 需要登錄但未登錄
    if user is None and require_login:
        raise HTTPException(status_code=401, detail="[TIP] 請先登錄")

    WINDOW = 3600  # 滑動窗口大小：1 小時
    now = int(time.time())
    cutoff = now - WINDOW  # 窗口起始時間戳

    # 已登錄用戶的 IP 限額與用戶名一致，遊客使用較低的 IP 限額
    ip_limit = MAX_USER_REQUESTS_PER_HOUR if user else MAX_IP_REQUESTS_PER_HOUR

    try:
        ip_key = None
        ip_member = None
        user_id = user.id if user else None

        rate_limit_debug(
            "request",
            path=path,
            ip=ip_address,
            user_id=user_id,
            require_login=require_login,
            ip_limit=ip_limit,
            user_limit=MAX_USER_REQUESTS_PER_HOUR if user else None,
        )

        # === 步驟 A：始終記錄並檢查 IP 計數 ===
        if ip_address:
            ip_key = f"rl:ip:{ip_address}"
            # 用時間戳作為 score，member 必須真正唯一，否則會覆蓋同秒內的舊記錄。
            ip_member = _make_rate_limit_member(now)
            await redis_client.zadd(ip_key, {ip_member: now})
            await redis_client.zremrangebyscore(ip_key, 0, cutoff)
            await redis_client.expire(ip_key, WINDOW + 60)
            ip_count = await redis_client.zcard(ip_key)
            rate_limit_debug(
                "ip_counter",
                path=path,
                ip=ip_address,
                user_id=user_id,
                key=ip_key,
                count=ip_count,
                limit=ip_limit,
            )

            if ip_count > ip_limit:
                rate_limit_debug(
                    "ip_limit_exceeded",
                    path=path,
                    ip=ip_address,
                    user_id=user_id,
                    key=ip_key,
                    count=ip_count,
                    limit=ip_limit,
                )
                await _rollback_rate_limit_member(ip_key, ip_member)
                if user is None:
                    await _raise_redis_rate_limit(
                        key=ip_key,
                        count=ip_count,
                        limit=ip_limit,
                        window_seconds=WINDOW,
                        now=now,
                        limit_type="guest_ip_limit",
                        scope="ip",
                        message="游客请求已达每小时上限，请稍后再试。登录账号后可继续查询。",
                        suggest_login=True,
                    )
                else:
                    await _raise_redis_rate_limit(
                        key=ip_key,
                        count=ip_count,
                        limit=ip_limit,
                        window_seconds=WINDOW,
                        now=now,
                        limit_type="authenticated_ip_limit",
                        scope="ip",
                        message="该 IP 请求已达每小时上限，请稍后再试。",
                    )

        # === 步驟 B：已登錄用戶額外檢查用戶計數 ===
        if user:
            user_key = f"rl:user:{user.id}"
            user_member = _make_rate_limit_member(now)
            await redis_client.zadd(user_key, {user_member: now})
            await redis_client.zremrangebyscore(user_key, 0, cutoff)
            await redis_client.expire(user_key, WINDOW + 60)
            user_count = await redis_client.zcard(user_key)
            rate_limit_debug(
                "user_counter",
                path=path,
                ip=ip_address,
                user_id=user_id,
                key=user_key,
                count=user_count,
                limit=MAX_USER_REQUESTS_PER_HOUR,
            )

            if user_count > MAX_USER_REQUESTS_PER_HOUR:
                rate_limit_debug(
                    "user_limit_exceeded",
                    path=path,
                    ip=ip_address,
                    user_id=user_id,
                    key=user_key,
                    count=user_count,
                    limit=MAX_USER_REQUESTS_PER_HOUR,
                )
                await _rollback_rate_limit_member(user_key, user_member)
                await _rollback_rate_limit_member(ip_key, ip_member)
                await _raise_redis_rate_limit(
                    key=user_key,
                    count=user_count,
                    limit=MAX_USER_REQUESTS_PER_HOUR,
                    window_seconds=WINDOW,
                    now=now,
                    limit_type="authenticated_user_limit",
                    scope="user",
                    message="当前账号请求已达每小时上限，请稍后再试。",
                )

    except HTTPException:
        raise
    except Exception as e:
        # Redis 故障時降級：記錄警告但不阻斷服務
        print(f"[WARN] Redis 限流失敗，降級為不限流: {e}")
        pass
def _get_login_retry_after_seconds(
    db: Session,
    *,
    ip: str,
    login_attempts: int,
) -> Optional[int]:
    """
    Estimate when the next login attempt can pass the 1-minute sliding window.

    Login rate-limit checks happen before writing the current attempt, so
    `login_attempts` only counts already-recorded rows.
    """
    overflow = login_attempts - MAX_LOGIN_PER_MINUTE + 1
    if overflow <= 0:
        overflow = 1

    login_paths = ["/login", "/auth/login", "/api/auth/login"]

    target_row = db.query(ApiUsageLog.called_at).filter(
        ApiUsageLog.ip == ip,
        ApiUsageLog.path.in_(login_paths),
    ).order_by(ApiUsageLog.called_at.asc()).offset(overflow - 1).first()

    if not target_row or not target_row[0]:
        return None

    release_at = target_row[0] + timedelta(minutes=1)
    retry_after_seconds = max(0, int((release_at - utils.now_utc_naive()).total_seconds()))
    return max(1, retry_after_seconds)


def check_login_rate_limit(db: Session, ip: str):
    one_minute_ago = utils.now_utc_naive() - timedelta(minutes=1)
    login_paths = ["/login", "/auth/login", "/api/auth/login"]

    login_attempts = db.query(ApiUsageLog).filter(
        ApiUsageLog.ip == ip,
        ApiUsageLog.path.in_(login_paths),
        ApiUsageLog.called_at >= one_minute_ago,
    ).count()

    if login_attempts >= MAX_LOGIN_PER_MINUTE:
        _raise_login_rate_limit(db, ip=ip, login_attempts=login_attempts)
