"""
API usage stats service.
"""

import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from app.common.path import LOGS_DATABASE_PATH


def _to_db_time(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return str(value)


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def _pick_first_existing_column(
    cursor: sqlite3.Cursor,
    table_name: str,
    candidates: list[str],
) -> Optional[str]:
    for column in candidates:
        if _column_exists(cursor, table_name, column):
            return column
    return None


def _safe_count(cursor: sqlite3.Cursor, query: str, params: tuple = ()) -> int:
    try:
        cursor.execute(query, params)
        row = cursor.fetchone()
        if not row or row[0] is None:
            return 0
        return int(row[0])
    except sqlite3.Error:
        return 0


def get_api_usage_stats(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Get API usage counters with schema fallback."""
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    try:
        cursor = db.cursor()

        if not _table_exists(cursor, "api_usage_logs"):
            return {
                "total_calls": 0,
                "unique_users": 0,
                "unique_ips": 0,
            }

        time_column = _pick_first_existing_column(
            cursor,
            "api_usage_logs",
            ["called_at", "timestamp", "created_at"],
        )
        ip_column = _pick_first_existing_column(
            cursor, "api_usage_logs", ["ip", "ip_address"])

        where_clause = ""
        params: list[Any] = []

        start_value = _to_db_time(start_time)
        end_value = _to_db_time(end_time)

        if time_column and start_value and end_value:
            where_clause = f"WHERE {time_column} BETWEEN ? AND ?"
            params.extend([start_value, end_value])
        elif time_column and start_value:
            where_clause = f"WHERE {time_column} >= ?"
            params.append(start_value)
        elif time_column and end_value:
            where_clause = f"WHERE {time_column} <= ?"
            params.append(end_value)

        total_calls = _safe_count(
            cursor,
            f"SELECT COUNT(*) FROM api_usage_logs {where_clause}",
            tuple(params),
        )

        unique_users = 0
        if _column_exists(cursor, "api_usage_logs", "user_id"):
            user_where_clause = (
                f"{where_clause} AND user_id IS NOT NULL"
                if where_clause
                else "WHERE user_id IS NOT NULL"
            )
            unique_users = _safe_count(
                cursor,
                f"SELECT COUNT(DISTINCT user_id) FROM api_usage_logs {user_where_clause}",
                tuple(params),
            )

        unique_ips = 0
        if ip_column:
            unique_ips = _safe_count(
                cursor,
                f"SELECT COUNT(DISTINCT {ip_column}) FROM api_usage_logs {where_clause}",
                tuple(params),
            )

        return {
            "total_calls": total_calls,
            "unique_users": unique_users,
            "unique_ips": unique_ips,
        }
    finally:
        db.close()


def get_stats_summary() -> Dict[str, Any]:
    """Get summary stats with missing-table fallback."""
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    try:
        cursor = db.cursor()

        total_api_calls = 0
        unique_users = 0
        unique_ips = 0
        total_keyword_searches = 0
        total_page_visits = 0

        if _table_exists(cursor, "api_usage_logs"):
            total_api_calls = _safe_count(cursor, "SELECT COUNT(*) FROM api_usage_logs")

            if _column_exists(cursor, "api_usage_logs", "user_id"):
                unique_users = _safe_count(
                    cursor,
                    "SELECT COUNT(DISTINCT user_id) FROM api_usage_logs WHERE user_id IS NOT NULL",
                )

            ip_column = _pick_first_existing_column(
                cursor, "api_usage_logs", ["ip", "ip_address"]
            )
            if ip_column:
                unique_ips = _safe_count(
                    cursor,
                    f"SELECT COUNT(DISTINCT {ip_column}) FROM api_usage_logs",
                )

        if _table_exists(cursor, "api_keyword_log"):
            total_keyword_searches = _safe_count(
                cursor, "SELECT COUNT(*) FROM api_keyword_log"
            )

        if _table_exists(cursor, "api_visit_log"):
            has_date = _column_exists(cursor, "api_visit_log", "date")
            if has_date:
                total_page_visits = _safe_count(
                    cursor,
                    "SELECT COALESCE(SUM(count), 0) FROM api_visit_log WHERE date IS NULL",
                )
            else:
                total_page_visits = _safe_count(
                    cursor,
                    "SELECT COALESCE(SUM(count), 0) FROM api_visit_log",
                )

        return {
            "total_api_calls": total_api_calls,
            "total_keyword_searches": total_keyword_searches,
            "total_page_visits": total_page_visits,
            "unique_users": unique_users,
            "unique_ips": unique_ips,
        }
    finally:
        db.close()


def get_field_stats(field: str) -> Dict[str, Any]:
    """Get grouped top values for a field in api_usage_logs."""
    allowed_fields = ["path", "method", "user_id", "ip_address", "status_code"]
    if field not in allowed_fields:
        raise ValueError(f"Invalid field: {field}. Allowed fields: {allowed_fields}")

    db = sqlite3.connect(LOGS_DATABASE_PATH)
    try:
        cursor = db.cursor()

        if not _table_exists(cursor, "api_usage_logs"):
            return {"field": field, "total": 0, "top_values": []}

        if field == "ip_address":
            actual_field = _pick_first_existing_column(
                cursor, "api_usage_logs", ["ip_address", "ip"]
            )
            if not actual_field:
                return {"field": field, "total": 0, "top_values": []}
        else:
            actual_field = field
            if not _column_exists(cursor, "api_usage_logs", actual_field):
                return {"field": field, "total": 0, "top_values": []}

        query = f"""
            SELECT {actual_field}, COUNT(*) as count
            FROM api_usage_logs
            WHERE {actual_field} IS NOT NULL
            GROUP BY {actual_field}
            ORDER BY count DESC
            LIMIT 20
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        cursor.execute(
            f"SELECT COUNT(*) FROM api_usage_logs WHERE {actual_field} IS NOT NULL"
        )
        total_row = cursor.fetchone()
        total = int(total_row[0]) if total_row and total_row[0] is not None else 0

        return {
            "field": field,
            "total": total,
            "top_values": [
                {
                    "value": row[0],
                    "count": row[1],
                    "percentage": round((row[1] / total) * 100, 2) if total > 0 else 0,
                }
                for row in rows
            ],
        }
    finally:
        db.close()
