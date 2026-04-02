"""
Keyword statistics business logic.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.common.path import LOGS_DATABASE_PATH
from app.common.time_utils import now_shanghai, shanghai_to_utc_naive, to_shanghai_iso


def _normalize_query_time(value: Optional[datetime]) -> Optional[datetime]:
    return shanghai_to_utc_naive(value)


def get_top_keywords(
    limit: int = 10,
    days: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Get top keywords."""
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    where_clause = ""
    params: list[Any] = []

    if days:
        cutoff_time = shanghai_to_utc_naive(now_shanghai() - timedelta(days=days))
        where_clause = "WHERE timestamp >= ?"
        params.append(cutoff_time)
    elif start_time and end_time:
        where_clause = "WHERE timestamp BETWEEN ? AND ?"
        params.extend([_normalize_query_time(start_time), _normalize_query_time(end_time)])
    elif start_time:
        where_clause = "WHERE timestamp >= ?"
        params.append(_normalize_query_time(start_time))
    elif end_time:
        where_clause = "WHERE timestamp <= ?"
        params.append(_normalize_query_time(end_time))

    query = f"""
        SELECT value, COUNT(*) as count
        FROM api_keyword_log
        {where_clause}
        GROUP BY value
        ORDER BY count DESC
        LIMIT ?
    """
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    total_query = f"""
        SELECT COUNT(*)
        FROM api_keyword_log
        {where_clause}
    """
    cursor.execute(total_query, params[:-1])
    total = cursor.fetchone()[0]

    db.close()

    return [
        {
            "keyword": row[0],
            "count": row[1],
            "percentage": round(row[1] / total * 100, 2) if total > 0 else 0,
        }
        for row in rows
    ]


def search_keyword_logs(
    keyword: Optional[str] = None,
    user_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """Search keyword logs."""
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    where_clauses = []
    params: list[Any] = []

    if keyword:
        where_clauses.append("(value LIKE ? OR field LIKE ? OR path LIKE ?)")
        like_pattern = f"%{keyword}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    if user_id is not None:
        where_clauses.append("(field = ? AND value = ?)")
        params.extend(["user_id", str(user_id)])

    if start_time:
        where_clauses.append("timestamp >= ?")
        params.append(_normalize_query_time(start_time))

    if end_time:
        where_clauses.append("timestamp <= ?")
        params.append(_normalize_query_time(end_time))

    where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    count_query = f"""
        SELECT COUNT(*)
        FROM api_keyword_log
        {where_clause}
    """
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    data_query = f"""
        SELECT id, value, field, timestamp, path
        FROM api_keyword_log
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(data_query, params + [page_size, offset])
    rows = cursor.fetchall()

    db.close()

    logs = []
    for row in rows:
        field_name = row[2]
        value = row[1]
        logs.append(
            {
                "id": row[0],
                "keyword": value,
                "value": value,
                "field": field_name,
                "timestamp": to_shanghai_iso(row[3], sep=" "),
                "path": row[4],
                "user_id": int(value) if field_name == "user_id" and str(value).isdigit() else None,
                "ip_address": value if field_name in {"ip", "ip_address"} else None,
            }
        )

    return {
        "logs": logs,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

