from __future__ import annotations

from typing import Optional

from app.redis_client import sync_redis_client

ONLINE_TIME_WINDOW_SECONDS = 60
ONLINE_TIME_SESSION_LIMIT = 24
ONLINE_TIME_USER_LIMIT = 60
ONLINE_TIME_IP_LIMIT = 120


def _increment_window_counter(key: str, window_seconds: int) -> int:
    count = int(sync_redis_client.incr(key))
    if count == 1:
        sync_redis_client.expire(key, window_seconds)
    return count


def check_online_time_report_limits(
    *,
    session_id: Optional[str],
    user_id: int,
    ip_address: Optional[str],
) -> tuple[bool, Optional[dict]]:
    """
    Apply lightweight Redis-backed admission control for report-online-time.

    This is intentionally a coarse protection layer:
    - it does not deduplicate payload content
    - it only limits burst frequency per session, user, and IP
    - it fails open if Redis is unavailable
    """
    try:
        if session_id:
            session_key = f"ot:session:{session_id}"
            session_count = _increment_window_counter(session_key, ONLINE_TIME_WINDOW_SECONDS)
            if session_count > ONLINE_TIME_SESSION_LIMIT:
                return False, {
                    "code": "online_time_rate_limited",
                    "scope": "session",
                    "retry_after_seconds": ONLINE_TIME_WINDOW_SECONDS,
                    "message": "Too many online time reports for this session",
                }

        user_key = f"ot:user:{user_id}"
        user_count = _increment_window_counter(user_key, ONLINE_TIME_WINDOW_SECONDS)
        if user_count > ONLINE_TIME_USER_LIMIT:
            return False, {
                "code": "online_time_rate_limited",
                "scope": "user",
                "retry_after_seconds": ONLINE_TIME_WINDOW_SECONDS,
                "message": "Too many online time reports for this user",
            }

        if ip_address:
            ip_key = f"ot:ip:{ip_address}"
            ip_count = _increment_window_counter(ip_key, ONLINE_TIME_WINDOW_SECONDS)
            if ip_count > ONLINE_TIME_IP_LIMIT:
                return False, {
                    "code": "online_time_rate_limited",
                    "scope": "ip",
                    "retry_after_seconds": ONLINE_TIME_WINDOW_SECONDS,
                    "message": "Too many online time reports from this IP",
                }
    except Exception as exc:
        print(f"[WARN] online time Redis guard failed open: {exc}")
        return True, None

    return True, None
