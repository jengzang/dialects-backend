"""
小时级和每日级统计业务逻辑

提供小时级、每日级的 API 调用统计数据查询
"""

import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.common.path import LOGS_DATABASE_PATH


def get_hourly_trend(hours: int = 24) -> Dict[str, Any]:
    """
    获取小时级调用趋势

    Args:
        hours: 最近N小时，默认24小时，最多7天（168小时）

    Returns:
        小时级调用数据和汇总统计
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 计算起始时间
    start_time = datetime.now() - timedelta(hours=hours)
    start_hour = start_time.replace(minute=0, second=0, microsecond=0)

    # 查询数据
    cursor.execute("""
        SELECT hour, total_calls
        FROM api_usage_hourly
        WHERE hour >= ?
        ORDER BY hour ASC
    """, (start_hour,))

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
                "peak_calls": 0
            }
        }

    # 构建数据点
    data = [
        {"hour": row[0], "total_calls": row[1]}
        for row in rows
    ]

    # 计算汇总统计
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
            "peak_calls": peak_row[1]
        }
    }


def get_daily_trend(
    days: int = 30,
    path: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取每日调用趋势

    Args:
        days: 最近N天，默认30天，最多365天
        path: 指定API路径（可选），不指定则返回所有API的总和

    Returns:
        每日调用数据和汇总统计
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 计算起始日期
    start_date = (datetime.now() - timedelta(days=days)).date()

    if path:
        # 查询指定API的每日数据
        cursor.execute("""
            SELECT date, call_count
            FROM api_usage_daily
            WHERE date >= ? AND path = ?
            ORDER BY date ASC
        """, (start_date, path))

        rows = cursor.fetchall()

        # 指定API时，unique_apis 始终为 1
        unique_apis = 1 if rows else 0
    else:
        # 查询所有API的每日总和
        cursor.execute("""
            SELECT date, SUM(call_count) as total_calls
            FROM api_usage_daily
            WHERE date >= ?
            GROUP BY date
            ORDER BY date ASC
        """, (start_date,))

        rows = cursor.fetchall()

        # 查询该时间段内有多少个独特的API
        cursor.execute("""
            SELECT COUNT(DISTINCT path)
            FROM api_usage_daily
            WHERE date >= ?
        """, (start_date,))
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
                "peak_calls": 0
            }
        }

    # 构建数据点
    data = [
        {"date": str(row[0]), "total_calls": row[1]}
        for row in rows
    ]

    # 计算汇总统计
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
            "peak_calls": peak_row[1]
        }
    }


def get_api_ranking(
    date: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    获取 API 排行榜

    Args:
        date: 指定日期（YYYY-MM-DD），与 days 互斥
        days: 最近N天的排行榜，与 date 互斥
        limit: 返回前N个，默认10个，最多100个

    Returns:
        API 排行榜和总调用数
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 参数验证
    if date and days:
        db.close()
        raise ValueError("date 和 days 参数不能同时使用")

    # 确定查询条件
    if date:
        # 场景 1：查询指定日期
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            db.close()
            raise ValueError("日期格式错误，应为 YYYY-MM-DD")

        where_clause = "WHERE date = ?"
        where_params = (target_date,)
        period_label = str(target_date)

    elif days:
        # 场景 2：查询最近N天
        start_date = (datetime.now() - timedelta(days=days)).date()
        where_clause = "WHERE date >= ?"
        where_params = (start_date,)
        period_label = f"last_{days}_days"

    else:
        # 场景 3：查询所有时间
        where_clause = ""
        where_params = ()
        period_label = "all_time"

    # 查询 API 排行（按总调用数聚合）
    if where_clause:
        cursor.execute(f"""
            SELECT path, SUM(call_count) as total_calls
            FROM api_usage_daily
            {where_clause}
            GROUP BY path
            ORDER BY total_calls DESC
            LIMIT ?
        """, where_params + (limit,))
    else:
        cursor.execute("""
            SELECT path, SUM(call_count) as total_calls
            FROM api_usage_daily
            GROUP BY path
            ORDER BY total_calls DESC
            LIMIT ?
        """, (limit,))

    rows = cursor.fetchall()

    # 查询独特API数量
    if where_clause:
        cursor.execute(f"""
            SELECT COUNT(DISTINCT path)
            FROM api_usage_daily
            {where_clause}
        """, where_params)
    else:
        cursor.execute("""
            SELECT COUNT(DISTINCT path)
            FROM api_usage_daily
        """)
    unique_apis = cursor.fetchone()[0]

    # 查询总调用数（所有API）
    if where_clause:
        cursor.execute(f"""
            SELECT SUM(call_count)
            FROM api_usage_daily
            {where_clause}
        """, where_params)
    else:
        cursor.execute("""
            SELECT SUM(call_count)
            FROM api_usage_daily
        """)
    total_calls_all = cursor.fetchone()[0] or 0

    db.close()

    if not rows:
        return {
            "period": period_label,
            "ranking": [],
            "total_calls": 0,
            "unique_apis": 0
        }

    # 计算 Top N 的调用数
    total_calls_top = sum(row[1] for row in rows)

    # 构建排行榜
    ranking = [
        {
            "rank": idx + 1,
            "path": row[0],
            "call_count": row[1],
            "percentage": round(row[1] / total_calls_all * 100, 1) if total_calls_all > 0 else 0
        }
        for idx, row in enumerate(rows)
    ]

    return {
        "period": period_label,
        "ranking": ranking,
        "total_calls": total_calls_all,
        "unique_apis": unique_apis,
        "top_n_calls": total_calls_top,
        "top_n_percentage": round(total_calls_top / total_calls_all * 100, 1) if total_calls_all > 0 else 0
    }


def get_api_history(path: str, days: int = 30) -> Dict[str, Any]:
    """
    获取指定 API 的历史趋势

    Args:
        path: API路径（必填）
        days: 最近N天，默认30天，最多365天

    Returns:
        指定API的历史调用数据和汇总统计
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 计算起始日期
    start_date = (datetime.now() - timedelta(days=days)).date()

    # 查询指定API的历史数据
    cursor.execute("""
        SELECT date, call_count
        FROM api_usage_daily
        WHERE date >= ? AND path = ?
        ORDER BY date ASC
    """, (start_date, path))

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
                "peak_calls": 0
            }
        }

    # 构建数据点
    data = [
        {"date": str(row[0]), "call_count": row[1]}
        for row in rows
    ]

    # 计算汇总统计
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
            "peak_calls": peak_row[1]
        }
    }
