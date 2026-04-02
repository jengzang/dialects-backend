from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

UTC = timezone.utc
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def today_shanghai() -> date:
    return now_shanghai().date()


def _parse_datetime(value: Optional[datetime | str]) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def assume_utc(value: Optional[datetime | str]) -> Optional[datetime]:
    dt = _parse_datetime(value)
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def assume_shanghai(value: Optional[datetime | str]) -> Optional[datetime]:
    dt = _parse_datetime(value)
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=SHANGHAI_TZ)
    return dt.astimezone(SHANGHAI_TZ)


def to_shanghai_datetime(value: Optional[datetime | str]) -> Optional[datetime]:
    dt = assume_utc(value)
    if dt is None:
        return None
    return dt.astimezone(SHANGHAI_TZ)


def to_shanghai_iso(
    value: Optional[datetime | str],
    *,
    sep: str = "T",
    timespec: str = "seconds",
) -> Optional[str]:
    dt = to_shanghai_datetime(value)
    if dt is None:
        return None
    return dt.isoformat(sep=sep, timespec=timespec)


def to_shanghai_bucket_datetime(value: datetime) -> datetime:
    dt = to_shanghai_datetime(value)
    if dt is None:
        raise ValueError("value cannot be None")
    return dt.replace(tzinfo=None)


def to_shanghai_bucket_hour(value: datetime) -> datetime:
    local_dt = to_shanghai_bucket_datetime(value)
    return local_dt.replace(minute=0, second=0, microsecond=0)


def to_shanghai_bucket_date(value: datetime) -> date:
    return to_shanghai_bucket_datetime(value).date()


def shanghai_to_utc_naive(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        localized = value.replace(tzinfo=SHANGHAI_TZ)
    else:
        localized = value.astimezone(SHANGHAI_TZ)
    return localized.astimezone(UTC).replace(tzinfo=None)
