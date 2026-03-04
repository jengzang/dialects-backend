"""
API 使用统计业务逻辑

提供 API 使用统计、字段统计等功能的纯业务逻辑实现
"""

import sqlite3
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.common.path import LOGS_DATABASE_PATH


def get_api_usage_stats(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    获取 API 使用统计

    Args:
        start_time: 起始时间
        end_time: 结束时间

    Returns:
        包含总调用数、独特用户数、独特IP数等统计信息
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 构建时间过滤条件
    where_clause = ""
    params = []

    if start_time and end_time:
        where_clause = "WHERE timestamp BETWEEN ? AND ?"
        params.extend([start_time, end_time])
    elif start_time:
        where_clause = "WHERE timestamp >= ?"
        params.append(start_time)
    elif end_time:
        where_clause = "WHERE timestamp <= ?"
        params.append(end_time)

    # 总调用数
    cursor.execute(f"SELECT COUNT(*) FROM api_usage_logs {where_clause}", params)
    total_calls = cursor.fetchone()[0]

    # 独特用户数
    cursor.execute(
        f"SELECT COUNT(DISTINCT user_id) FROM api_usage_logs {where_clause} AND user_id IS NOT NULL",
        params
    )
    unique_users = cursor.fetchone()[0]

    # 独特IP数
    cursor.execute(f"SELECT COUNT(DISTINCT ip_address) FROM api_usage_logs {where_clause}", params)
    unique_ips = cursor.fetchone()[0]

    db.close()

    return {
        "total_calls": total_calls,
        "unique_users": unique_users,
        "unique_ips": unique_ips
    }


def get_stats_summary() -> Dict[str, Any]:
    """
    获取统计概览

    Returns:
        包含各类统计数据的概览信息
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # API 调用总数
    cursor.execute("SELECT COUNT(*) FROM api_usage_logs")
    total_api_calls = cursor.fetchone()[0]

    # 关键词搜索总数
    cursor.execute("SELECT COUNT(*) FROM keyword_logs")
    total_keyword_searches = cursor.fetchone()[0]

    # 页面访问总数
    cursor.execute("SELECT SUM(visit_count) FROM html_visits")
    result = cursor.fetchone()
    total_page_visits = result[0] if result and result[0] else 0

    # 独特用户数
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM api_usage_logs WHERE user_id IS NOT NULL")
    unique_users = cursor.fetchone()[0]

    # 独特IP数
    cursor.execute("SELECT COUNT(DISTINCT ip_address) FROM api_usage_logs")
    unique_ips = cursor.fetchone()[0]

    db.close()

    return {
        "total_api_calls": total_api_calls,
        "total_keyword_searches": total_keyword_searches,
        "total_page_visits": total_page_visits,
        "unique_users": unique_users,
        "unique_ips": unique_ips
    }


def get_field_stats(field: str) -> Dict[str, Any]:
    """
    获取指定字段的统计信息

    Args:
        field: 字段名（如 path, method, user_id 等）

    Returns:
        字段统计信息，包含 top 值和计数
    """
    # 验证字段名（防止SQL注入）
    allowed_fields = ["path", "method", "user_id", "ip_address", "status_code"]
    if field not in allowed_fields:
        raise ValueError(f"Invalid field: {field}. Allowed fields: {allowed_fields}")

    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 查询字段统计
    query = f"""
        SELECT {field}, COUNT(*) as count
        FROM api_usage_logs
        WHERE {field} IS NOT NULL
        GROUP BY {field}
        ORDER BY count DESC
        LIMIT 20
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    # 总数
    cursor.execute(f"SELECT COUNT(*) FROM api_usage_logs WHERE {field} IS NOT NULL")
    total = cursor.fetchone()[0]

    db.close()

    return {
        "field": field,
        "total": total,
        "top_values": [
            {
                "value": row[0],
                "count": row[1],
                "percentage": round(row[1] / total * 100, 2) if total > 0 else 0
            }
            for row in rows
        ]
    }
