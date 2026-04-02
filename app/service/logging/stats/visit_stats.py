"""
Visit statistics business logic.
"""

import sqlite3
from datetime import timedelta
from typing import Any, Dict, List, Optional

from starlette.concurrency import run_in_threadpool

from app.common.path import LOGS_DATABASE_PATH
from app.common.time_utils import today_shanghai, to_shanghai_iso
from app.sql.db_pool import get_db_pool


def _sync_total_visits() -> int:
    pool = get_db_pool(LOGS_DATABASE_PATH)
    with pool.get_connection() as conn:
        result = conn.execute(
            "SELECT SUM(count) FROM api_visit_log WHERE date IS NULL"
        ).fetchone()
    return result[0] if result and result[0] else 0


def _sync_today_visits() -> int:
    pool = get_db_pool(LOGS_DATABASE_PATH)
    today = today_shanghai()
    tomorrow = today + timedelta(days=1)
    with pool.get_connection() as conn:
        result = conn.execute(
            "SELECT SUM(count) FROM api_visit_log WHERE date >= ? AND date < ?",
            (today.isoformat(), tomorrow.isoformat()),
        ).fetchone()
    return result[0] if result and result[0] else 0


async def get_total_visits() -> int:
    """Get total visits."""
    return await run_in_threadpool(_sync_total_visits)


async def get_today_visits() -> int:
    """Get today's visits using Asia/Shanghai day boundaries."""
    return await run_in_threadpool(_sync_today_visits)


def get_visit_history(
    path: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Get daily visit history."""
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    where_clauses = ["date IS NOT NULL"]
    params: list[Any] = []

    if path:
        where_clauses.append("path = ?")
        params.append(path)

    if start_date:
        where_clauses.append("date(date) >= ?")
        params.append(start_date)

    if end_date:
        where_clauses.append("date(date) <= ?")
        params.append(end_date)

    where_clause = " AND ".join(where_clauses)

    count_query = f"""
        SELECT COUNT(*)
        FROM api_visit_log
        WHERE {where_clause}
    """
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    data_query = f"""
        SELECT id, path, date, count, updated_at
        FROM api_visit_log
        WHERE {where_clause}
        ORDER BY date DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(data_query, params + [limit, offset])
    rows = cursor.fetchall()

    db.close()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": [
            {
                "id": row[0],
                "path": row[1],
                "date": row[2][:10] if row[2] else None,
                "count": row[3],
                "updated_at": to_shanghai_iso(row[4], sep=" "),
            }
            for row in rows
        ],
    }


def get_visits_by_path(days: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Get visit counts grouped by path."""
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    start_date = None
    if days:
        start_date = (today_shanghai() - timedelta(days=days)).isoformat()
        query = """
            SELECT path, SUM(count) as total_visits
            FROM api_visit_log
            WHERE date IS NOT NULL AND date >= ?
            GROUP BY path
            ORDER BY total_visits DESC
            LIMIT ?
        """
        params = (start_date, limit)
    else:
        query = """
            SELECT path, count as total_visits
            FROM api_visit_log
            WHERE date IS NULL
            ORDER BY total_visits DESC
            LIMIT ?
        """
        params = (limit,)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    if days and start_date is not None:
        cursor.execute(
            """
            SELECT SUM(count)
            FROM api_visit_log
            WHERE date IS NOT NULL AND date >= ?
            """,
            (start_date,),
        )
    else:
        cursor.execute("SELECT SUM(count) FROM api_visit_log WHERE date IS NULL")

    total = cursor.fetchone()[0] or 0

    db.close()

    return [
        {
            "path": row[0],
            "visit_count": row[1],
            "percentage": round(row[1] / total * 100, 2) if total > 0 else 0,
        }
        for row in rows
    ]

