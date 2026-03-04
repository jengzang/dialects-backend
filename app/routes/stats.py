"""
API 调用统计查询接口

提供小时级、每日级的 API 调用统计数据查询
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel
import sqlite3

from app.common.path import LOGS_DATABASE_PATH


router = APIRouter(prefix="/logs/stats", tags=["日志统计"])


# === Response Models ===

class HourlyDataPoint(BaseModel):
    hour: str
    total_calls: int


class DailyDataPoint(BaseModel):
    date: str
    total_calls: int


class ApiRankingItem(BaseModel):
    rank: int
    path: str
    call_count: int
    percentage: float


class ApiHistoryDataPoint(BaseModel):
    date: str
    call_count: int


class HourlySummary(BaseModel):
    total_calls: int
    avg_calls_per_hour: int
    peak_hour: Optional[str]
    peak_calls: int


class DailySummary(BaseModel):
    total_calls: int
    avg_calls_per_day: int
    peak_date: Optional[str]
    peak_calls: int


# === API Endpoints ===

@router.get("/hourly")
async def get_hourly_trend(hours: int = Query(24, ge=1, le=168)):
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


@router.get("/daily")
async def get_daily_trend(
    days: int = Query(30, ge=1, le=365),
    path: Optional[str] = None
):
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


@router.get("/ranking")
async def get_api_ranking(
    date: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100)
):
    """
    获取 API 排行榜

    Args:
        date: 指定日期（YYYY-MM-DD），默认今天
        limit: 返回前N个，默认10个，最多100个

    Returns:
        API 排行榜和总调用数
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 解析日期
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")
    else:
        target_date = datetime.now().date()

    # 查询指定日期的 API 排行
    cursor.execute("""
        SELECT path, call_count
        FROM api_usage_daily
        WHERE date = ?
        ORDER BY call_count DESC
        LIMIT ?
    """, (target_date, limit))

    rows = cursor.fetchall()

    # 查询该日期的所有独特API数量
    cursor.execute("""
        SELECT COUNT(DISTINCT path)
        FROM api_usage_daily
        WHERE date = ?
    """, (target_date,))
    unique_apis = cursor.fetchone()[0]

    # 查询该日期的总调用数（所有API）
    cursor.execute("""
        SELECT SUM(call_count)
        FROM api_usage_daily
        WHERE date = ?
    """, (target_date,))
    total_calls_all = cursor.fetchone()[0] or 0

    db.close()

    if not rows:
        return {
            "date": str(target_date),
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
        "date": str(target_date),
        "ranking": ranking,
        "total_calls": total_calls_all,
        "unique_apis": unique_apis,
        "top_n_calls": total_calls_top,
        "top_n_percentage": round(total_calls_top / total_calls_all * 100, 1) if total_calls_all > 0 else 0
    }


@router.get("/api-history")
async def get_api_history(
    path: str,
    days: int = Query(30, ge=1, le=365)
):
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

