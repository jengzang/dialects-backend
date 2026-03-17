"""
关键词统计业务逻辑

提供关键词查询、搜索等功能的纯业务逻辑实现
"""

import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.common.path import LOGS_DATABASE_PATH


def get_top_keywords(
    limit: int = 10,
    days: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    获取热门关键词

    Args:
        limit: 返回数量限制
        days: 最近N天（与start_time/end_time互斥）
        start_time: 起始时间
        end_time: 结束时间

    Returns:
        关键词列表，每项包含 keyword, count, percentage
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 构建时间过滤条件
    where_clause = ""
    params = []

    if days:
        cutoff_time = datetime.now() - timedelta(days=days)
        where_clause = "WHERE timestamp >= ?"
        params.append(cutoff_time)
    elif start_time and end_time:
        where_clause = "WHERE timestamp BETWEEN ? AND ?"
        params.extend([start_time, end_time])
    elif start_time:
        where_clause = "WHERE timestamp >= ?"
        params.append(start_time)
    elif end_time:
        where_clause = "WHERE timestamp <= ?"
        params.append(end_time)

    # 查询关键词统计
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

    # 计算总数用于百分比
    total_query = f"""
        SELECT COUNT(*)
        FROM api_keyword_log
        {where_clause}
    """
    cursor.execute(total_query, params[:-1])  # 不包含limit参数
    total = cursor.fetchone()[0]

    db.close()

    # 构建结果
    result = [
        {
            "keyword": row[0],
            "count": row[1],
            "percentage": round(row[1] / total * 100, 2) if total > 0 else 0
        }
        for row in rows
    ]

    return result


def search_keyword_logs(
    keyword: Optional[str] = None,
    user_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50
) -> Dict[str, Any]:
    """
    搜索关键词日志

    Args:
        keyword: 关键词（模糊匹配）
        user_id: 用户ID
        start_time: 起始时间
        end_time: 结束时间
        page: 页码
        page_size: 每页数量

    Returns:
        包含 logs 和 total 的字典
    """
    db = sqlite3.connect(LOGS_DATABASE_PATH)
    cursor = db.cursor()

    # 构建查询条件
    where_clauses = []
    params = []

    if keyword:
        where_clauses.append("(value LIKE ? OR field LIKE ? OR path LIKE ?)")
        like_pattern = f"%{keyword}%"
        params.extend([like_pattern, like_pattern, like_pattern])

    # api_keyword_log 表不包含 user_id 字段。
    # 为兼容旧接口语义，这里将 user_id 解释为参数日志中的字段值过滤。
    if user_id is not None:
        where_clauses.append("(field = ? AND value = ?)")
        params.extend(["user_id", str(user_id)])

    if start_time:
        where_clauses.append("timestamp >= ?")
        params.append(start_time)

    if end_time:
        where_clauses.append("timestamp <= ?")
        params.append(end_time)

    where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # 查询总数
    count_query = f"""
        SELECT COUNT(*)
        FROM api_keyword_log
        {where_clause}
    """
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # 查询分页数据
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

    # 构建结果
    logs = []
    for row in rows:
        field_name = row[2]
        value = row[1]
        logs.append(
            {
                "id": row[0],
                "keyword": value,  # 兼容旧字段
                "value": value,
                "field": field_name,
                "timestamp": row[3],
                "path": row[4],
                "user_id": int(value) if field_name == "user_id" and str(value).isdigit() else None,
                "ip_address": value if field_name in {"ip", "ip_address"} else None,
            }
        )

    return {
        "logs": logs,
        "total": total,
        "page": page,
        "page_size": page_size
    }
