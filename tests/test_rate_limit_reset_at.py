import os
import time
from datetime import datetime, timezone

from app.service.auth.core.dependencies import _build_rate_limit_detail


def test_reset_at_uses_utc_even_when_process_timezone_is_not_utc(monkeypatch):
    if not hasattr(time, "tzset"):
        return

    original_timezone = os.environ.get("TZ")
    try:
        monkeypatch.setenv("TZ", "Asia/Shanghai")
        time.tzset()

        before = int(datetime.now(timezone.utc).timestamp())
        detail = _build_rate_limit_detail(
            limit_type="guest_ip_limit",
            scope="ip",
            message="limited",
            limit=60,
            current_count=61,
            window_seconds=3600,
            retry_after_seconds=1857,
        )
        reset_timestamp = int(datetime.fromisoformat(detail["reset_at"].replace("Z", "+00:00")).timestamp())

        assert before + 1857 <= reset_timestamp <= int(datetime.now(timezone.utc).timestamp()) + 1857
    finally:
        if original_timezone is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", original_timezone)
        time.tzset()
