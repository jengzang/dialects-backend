"""
Hourly and daily API usage statistics.
"""

import sqlite3
from datetime import timedelta
from typing import Any, Dict, Optional

from app.common.path import LOGS_DATABASE_PATH
from app.common.time_utils import now_shanghai, today_shanghai


def get_hourly_trend(hours: int = 24) -> Dict[str, Any]:
    """Get hourly usage trend using Asia/Shanghai buckets."""
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    start_time = now_shanghai().replace(tzinfo=None) - timedelta(hours=hours)
    start_hour = start_time.replace(minute=0, second=0, microsecond=0)

    cursor.execute(
        """
        SELECT hour, total_calls
        FROM api_usage_hourly
        WHERE hour >= ?
        ORDER BY hour ASC
        """,
        (start_hour,),
    )
    rows = cursor.fetchall()
    db.close()

    if not rows:
        return {
            "period": f"{hours}h",
            "data": [],
            "summary": {
                "total_calls": 0,
                "avg_calls_per_hour": 0,
                "peak_hour": None,
                "peak_calls": 0,
            },
        }

    data = [{"hour": row[0], "total_calls": row[1]} for row in rows]
    total_calls = sum(row[1] for row in rows)
    avg_calls = total_calls // len(rows) if rows else 0
    peak_row = max(rows, key=lambda x: x[1])

    return {
        "period": f"{hours}h",
        "data": data,
        "summary": {
            "total_calls": total_calls,
            "avg_calls_per_hour": avg_calls,
            "peak_hour": peak_row[0],
            "peak_calls": peak_row[1],
        },
    }


def get_daily_trend(days: int = 30, path: Optional[str] = None) -> Dict[str, Any]:
    """Get daily usage trend using Asia/Shanghai dates."""
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    start_date = today_shanghai() - timedelta(days=days)

    if path:
        cursor.execute(
            """
            SELECT date, call_count
            FROM api_usage_daily
            WHERE date >= ? AND path = ?
            ORDER BY date ASC
            """,
            (start_date, path),
        )
        rows = cursor.fetchall()
        unique_apis = 1 if rows else 0
    else:
        cursor.execute(
            """
            SELECT date, SUM(call_count) as total_calls
            FROM api_usage_daily
            WHERE date >= ?
            GROUP BY date
            ORDER BY date ASC
            """,
            (start_date,),
        )
        rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT COUNT(DISTINCT path)
            FROM api_usage_daily
            WHERE date >= ?
            """,
            (start_date,),
        )
        unique_apis = cursor.fetchone()[0]

    db.close()

    if not rows:
        return {
            "period": f"{days}d",
            "path": path,
            "data": [],
            "summary": {
                "total_calls": 0,
                "unique_apis": 0,
                "avg_calls_per_day": 0,
                "peak_date": None,
                "peak_calls": 0,
            },
        }

    data = [{"date": str(row[0]), "total_calls": row[1]} for row in rows]
    total_calls = sum(row[1] for row in rows)
    avg_calls = total_calls // len(rows) if rows else 0
    peak_row = max(rows, key=lambda x: x[1])

    return {
        "period": f"{days}d",
        "path": path,
        "data": data,
        "summary": {
            "total_calls": total_calls,
            "unique_apis": unique_apis,
            "avg_calls_per_day": avg_calls,
            "peak_date": str(peak_row[0]),
            "peak_calls": peak_row[1],
        },
    }


def get_api_ranking(
    date: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Get API ranking for a date or recent days."""
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    if date and days:
        db.close()
        raise ValueError("date and days cannot be used together")

    if date:
        from datetime import datetime

        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as exc:
            db.close()
            raise ValueError("invalid date format, expected YYYY-MM-DD") from exc

        where_clause = "WHERE date = ?"
        where_params: tuple[Any, ...] = (target_date,)
        period_label = str(target_date)
    elif days:
        start_date = today_shanghai() - timedelta(days=days)
        where_clause = "WHERE date >= ?"
        where_params = (start_date,)
        period_label = f"last_{days}_days"
    else:
        where_clause = ""
        where_params = ()
        period_label = "all_time"

    if where_clause:
        cursor.execute(
            f"""
            SELECT path, SUM(call_count) as total_calls
            FROM api_usage_daily
            {where_clause}
            GROUP BY path
            ORDER BY total_calls DESC
            LIMIT ?
            """,
            where_params + (limit,),
        )
    else:
        cursor.execute(
            """
            SELECT path, SUM(call_count) as total_calls
            FROM api_usage_daily
            GROUP BY path
            ORDER BY total_calls DESC
            LIMIT ?
            """,
            (limit,),
        )
    rows = cursor.fetchall()

    if where_clause:
        cursor.execute(
            f"""
            SELECT COUNT(DISTINCT path)
            FROM api_usage_daily
            {where_clause}
            """,
            where_params,
        )
    else:
        cursor.execute("SELECT COUNT(DISTINCT path) FROM api_usage_daily")
    unique_apis = cursor.fetchone()[0]

    if where_clause:
        cursor.execute(
            f"""
            SELECT SUM(call_count)
            FROM api_usage_daily
            {where_clause}
            """,
            where_params,
        )
    else:
        cursor.execute("SELECT SUM(call_count) FROM api_usage_daily")
    total_calls_all = cursor.fetchone()[0] or 0

    db.close()

    if not rows:
        return {
            "period": period_label,
            "ranking": [],
            "total_calls": 0,
            "unique_apis": 0,
        }

    total_calls_top = sum(row[1] for row in rows)
    ranking = [
        {
            "rank": idx + 1,
            "path": row[0],
            "call_count": row[1],
            "percentage": round(row[1] / total_calls_all * 100, 1) if total_calls_all > 0 else 0,
        }
        for idx, row in enumerate(rows)
    ]

    return {
        "period": period_label,
        "ranking": ranking,
        "total_calls": total_calls_all,
        "unique_apis": unique_apis,
        "top_n_calls": total_calls_top,
        "top_n_percentage": round(total_calls_top / total_calls_all * 100, 1)
        if total_calls_all > 0
        else 0,
    }


def get_api_history(path: str, days: int = 30) -> Dict[str, Any]:
    """Get daily history for one API path."""
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    start_date = today_shanghai() - timedelta(days=days)
    cursor.execute(
        """
        SELECT date, call_count
        FROM api_usage_daily
        WHERE date >= ? AND path = ?
        ORDER BY date ASC
        """,
        (start_date, path),
    )
    rows = cursor.fetchall()
    db.close()

    if not rows:
        return {
            "path": path,
            "period": f"{days}d",
            "data": [],
            "summary": {
                "total_calls": 0,
                "avg_calls_per_day": 0,
                "peak_date": None,
                "peak_calls": 0,
            },
        }

    data = [{"date": str(row[0]), "call_count": row[1]} for row in rows]
    total_calls = sum(row[1] for row in rows)
    avg_calls = total_calls // len(rows) if rows else 0
    peak_row = max(rows, key=lambda x: x[1])

    return {
        "path": path,
        "period": f"{days}d",
        "data": data,
        "summary": {
            "total_calls": total_calls,
            "avg_calls_per_day": avg_calls,
            "peak_date": str(peak_row[0]),
            "peak_calls": peak_row[1],
        },
    }

