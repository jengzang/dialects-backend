"""
访问统计业务逻辑

提供页面访问统计、历史记录等功能的纯业务逻辑实现
"""

import sqlite3
from typing import List, Dict, Any, Optional
from datetime import date

from app.common.path import LOGS_DATABASE_PATH


def get_total_visits() -> int:
    """
    获取总访问量

    Returns:
        总访问次数
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 查询 date=NULL 的记录（总计）
    cursor.execute("SELECT SUM(count) FROM api_visit_log WHERE date IS NULL")
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
        "SELECT SUM(count) FROM api_visit_log WHERE date(date) = ?",
        (today,)
    )
    result = cursor.fetchone()

    db.close()

    return result[0] if result and result[0] else 0


def get_visit_history(
    path: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """
    获取访问历史

    Args:
        path: 筛选特定路径
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        limit: 返回数量
        offset: 分页偏移

    Returns:
        包含 total, offset, limit, data 的字典
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 构建查询条件
    where_clauses = ["date IS NOT NULL"]
    params = []

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

    # 查询总数
    count_query = f"""
        SELECT COUNT(*)
        FROM api_visit_log
        WHERE {where_clause}
    """
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # 查询数据
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
                "date": row[2][:10] if row[2] else None,  # 只取日期部分
                "count": row[3],
                "updated_at": row[4]
            }
            for row in rows
        ]
    }


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
            SELECT path, SUM(count) as total_visits
            FROM api_visit_log
            WHERE date IS NOT NULL AND date >= date('now', '-' || ? || ' days')
            GROUP BY path
            ORDER BY total_visits DESC
            LIMIT ?
        """
        params = (days, limit)
    else:
        # 查询总计（date IS NULL）
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

    # 计算总访问量用于百分比
    if days:
        cursor.execute(
            """
            SELECT SUM(count)
            FROM api_visit_log
            WHERE date IS NOT NULL AND date >= date('now', '-' || ? || ' days')
            """,
            (days,)
        )
    else:
        cursor.execute("SELECT SUM(count) FROM api_visit_log WHERE date IS NULL")

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

