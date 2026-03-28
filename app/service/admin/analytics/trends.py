"""
Recent Trends Analysis Module

Analyzes API usage trends from recent logs (7 days).
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.service.auth.database.models import ApiUsageLog


def get_recent_trends(
    db: Session,
    granularity: str = "day",
    days: int = 7
) -> dict:
    """
    Analyze recent API usage trends.

    Args:
        db: Database session
        granularity: 'day' or 'hour'
        days: Number of days to analyze (max 7)

    Returns:
        Dictionary with trend data
    """
    now = datetime.utcnow()
    start_date = now - timedelta(days=min(days, 7))

    # Query logs
    query = db.query(ApiUsageLog).filter(
        ApiUsageLog.called_at >= start_date
    )

    logs = query.all()

    if not logs:
        return {
            "period": f"{days}d",
            "granularity": granularity,
            "trends": [],
            "summary": {
                "total_calls": 0,
                "avg_daily_calls": 0,
                "peak_day": None
            }
        }

    # Group by time period
    trends_data = {}

    for log in logs:
        if not log.called_at:
            continue

        if granularity == "day":
            time_key = log.called_at.strftime("%Y-%m-%d")
        else:  # hour
            time_key = log.called_at.strftime("%Y-%m-%d %H:00")

        if time_key not in trends_data:
            trends_data[time_key] = {
                "time": time_key,
                "total_calls": 0,
                "active_users": set(),
                "durations": [],
                "api_calls": {}
            }

        trends_data[time_key]["total_calls"] += 1
        if log.user_id:
            trends_data[time_key]["active_users"].add(log.user_id)
        trends_data[time_key]["durations"].append(log.duration)

        # Track API calls
        api_path = log.path
        if api_path not in trends_data[time_key]["api_calls"]:
            trends_data[time_key]["api_calls"][api_path] = 0
        trends_data[time_key]["api_calls"][api_path] += 1

    # Process trends
    trends = []
    total_calls = 0
    peak_calls = 0
    peak_time = None

    for time_key in sorted(trends_data.keys()):
        data = trends_data[time_key]
        calls = data["total_calls"]
        total_calls += calls

        # Find top API for this period
        top_api = max(data["api_calls"].items(), key=lambda x: x[1])[0] if data["api_calls"] else None

        # Calculate average duration
        avg_duration = sum(data["durations"]) / len(data["durations"]) if data["durations"] else 0

        trend_item = {
            "time": time_key,
            "total_calls": calls,
            "active_users": len(data["active_users"]),
            "avg_duration": round(avg_duration, 3),
            "top_api": top_api
        }

        trends.append(trend_item)

        # Track peak
        if calls > peak_calls:
            peak_calls = calls
            peak_time = time_key

    # Calculate summary
    avg_daily_calls = total_calls / days if days > 0 else 0

    return {
        "period": f"{days}d",
        "granularity": granularity,
        "trends": trends,
        "summary": {
            "total_calls": total_calls,
            "avg_daily_calls": round(avg_daily_calls, 2),
            "peak_time": peak_time,
            "peak_calls": peak_calls
        }
    }
