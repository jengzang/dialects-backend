"""
访问统计业务逻辑

提供页面访问统计、历史记录等功能的纯业务逻辑实现
"""

import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime, date

from app.common.path import LOGS_DATABASE_PATH


def get_total_visits() -> int:
    """
    获取总访问量

    Returns:
        总访问次数
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    cursor.execute("SELECT SUM(visit_count) FROM html_visits")
    result = cursor.fetchone()

    db.close()

    return result[0] if result and result[0] else 0


def get_today_visits() -> int:
    """
    获取今日访问量

    Returns:
        今日访问次数
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    today = date.today()
    cursor.execute(
        "SELECT SUM(visit_count) FROM html_visits WHERE date = ?",
        (today,)
    )
    result = cursor.fetchone()

    db.close()

    return result[0] if result and result[0] else 0


def get_visit_history(days: int = 30) -> List[Dict[str, Any]]:
    """
    获取访问历史

    Args:
        days: 最近N天

    Returns:
        访问历史列表，每项包含 date 和 total_visits
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT date, SUM(visit_count) as total_visits
        FROM html_visits
        WHERE date >= date('now', '-' || ? || ' days')
        GROUP BY date
        ORDER BY date DESC
        """,
        (days,)
    )
    rows = cursor.fetchall()

    db.close()

    return [
        {
            "date": str(row[0]),
            "total_visits": row[1]
        }
        for row in rows
    ]


def get_visits_by_path(
    days: Optional[int] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    按路径统计访问量

    Args:
        days: 最近N天（可选）
        limit: 返回数量限制

    Returns:
        路径访问统计列表，每项包含 path, visit_count, percentage
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 构建查询
    if days:
        query = """
            SELECT path, SUM(visit_count) as total_visits
            FROM html_visits
            WHERE date >= date('now', '-' || ? || ' days')
            GROUP BY path
            ORDER BY total_visits DESC
            LIMIT ?
        """
        params = (days, limit)
    else:
        query = """
            SELECT path, SUM(visit_count) as total_visits
            FROM html_visits
            GROUP BY path
            ORDER BY total_visits DESC
            LIMIT ?
        """
        params = (limit,)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # 计算总访问量用于百分比
    if days:
        cursor.execute(
            """
            SELECT SUM(visit_count)
            FROM html_visits
            WHERE date >= date('now', '-' || ? || ' days')
            """,
            (days,)
        )
    else:
        cursor.execute("SELECT SUM(visit_count) FROM html_visits")

    total = cursor.fetchone()[0] or 0

    db.close()

    return [
        {
            "path": row[0],
            "visit_count": row[1],
            "percentage": round(row[1] / total * 100, 2) if total > 0 else 0
        }
        for row in rows
    ]
