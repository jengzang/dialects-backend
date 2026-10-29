"""Aggregate auth.db API usage by Beijing hour/day without loading raw logs."""

from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.common.time_utils import now_utc_naive
from app.service.auth.database.models import ApiUsageLog
from app.service.admin.monitoring.api_usage import LOGIN_PATHS


MAX_TREND_DAYS = 365


def get_recent_trends(db: Session, granularity: str = "day", days: int = 7) -> dict:
    """Return up to one year of usage, excluding the detail page's login paths.

    Two sequential SQL aggregates return at most one row per time bucket each.
    The largest hourly response has 8,761 buckets; raw log rows stay in SQLite.
    No background work, automatic retries, or additional workers are started.
    """
    if granularity not in ("hour", "day"):
        raise ValueError("granularity must be hour or day")
    if not 1 <= days <= MAX_TREND_DAYS:
        raise ValueError(f"days must be between 1 and {MAX_TREND_DAYS}")

    now = now_utc_naive()
    start = now - timedelta(days=days)
    date_format = "%Y-%m-%d" if granularity == "day" else "%Y-%m-%d %H:00"
    bucket = func.strftime(date_format, ApiUsageLog.called_at, "+8 hours")
    filters = (
        ApiUsageLog.called_at >= start,
        ApiUsageLog.called_at <= now,
        ~ApiUsageLog.path.in_(LOGIN_PATHS),
    )

    aggregates = db.query(
        bucket.label("time"),
        func.count(ApiUsageLog.id).label("total_calls"),
        func.count(func.distinct(ApiUsageLog.user_id)).label("active_users"),
        func.avg(ApiUsageLog.duration).label("avg_duration"),
    ).filter(*filters).group_by(bucket).order_by(bucket).all()

    summary = {
        "total_calls": 0,
        "avg_daily_calls": 0,
        "peak_time": None,
        "peak_calls": 0,
    }
    response = {
        "period": f"{days}d",
        "granularity": granularity,
        "trends": [],
        "summary": summary,
    }
    if not aggregates:
        return response

    # Rank within SQL so even high-cardinality paths do not cross into Python.
    path_counts = db.query(
        bucket.label("time"),
        ApiUsageLog.path.label("path"),
        func.count(ApiUsageLog.id).label("calls"),
    ).filter(*filters).group_by(bucket, ApiUsageLog.path).subquery()
    ranked = db.query(
        path_counts.c.time,
        path_counts.c.path,
        func.row_number().over(
            partition_by=path_counts.c.time,
            order_by=(path_counts.c.calls.desc(), path_counts.c.path.asc()),
        ).label("rank"),
    ).subquery()
    top_paths = dict(db.query(ranked.c.time, ranked.c.path).filter(ranked.c.rank == 1).all())

    by_time = {row.time: row for row in aggregates}
    cursor = (start + timedelta(hours=8)).replace(minute=0, second=0, microsecond=0)
    end = now + timedelta(hours=8)
    if granularity == "day":
        cursor = cursor.replace(hour=0)
    step = timedelta(days=1) if granularity == "day" else timedelta(hours=1)

    while cursor <= end:
        key = cursor.strftime(date_format)
        row = by_time.get(key)
        calls = row.total_calls if row else 0
        response["trends"].append({
            "time": key,
            "total_calls": calls,
            "active_users": row.active_users if row else 0,
            "avg_duration": round(float(row.avg_duration or 0), 3) if row else 0,
            "top_api": top_paths.get(key),
        })
        summary["total_calls"] += calls
        if calls > summary["peak_calls"]:
            summary["peak_calls"] = calls
            summary["peak_time"] = key
        cursor += step

    summary["avg_daily_calls"] = round(summary["total_calls"] / days, 2)
    return response
