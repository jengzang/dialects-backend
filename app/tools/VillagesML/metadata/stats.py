"""
元数据统计API
Metadata Statistics API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
import sqlite3
import os
from datetime import datetime

from ..dependencies import get_db, execute_query
from ..config import DB_PATH
from ..models import SystemOverview, TableInfo

router = APIRouter(prefix="/metadata/stats", tags=["metadata"])


@router.get("/overview", response_model=SystemOverview)
def get_system_overview(db: sqlite3.Connection = Depends(get_db)):
    """
    获取系统概览统计
    Get system overview statistics

    Returns:
        SystemOverview: 系统概览信息
    """
    # 获取村庄总数
    total_villages_query = "SELECT COUNT(*) as count FROM 广东省自然村"
    total_villages = execute_query(db, total_villages_query)[0]["count"]

    # 获取城市数量
    total_cities_query = "SELECT COUNT(DISTINCT 市级) as count FROM 广东省自然村"
    total_cities = execute_query(db, total_cities_query)[0]["count"]

    # 获取区县数量
    total_counties_query = "SELECT COUNT(DISTINCT 区县级) as count FROM 广东省自然村"
    total_counties = execute_query(db, total_counties_query)[0]["count"]

    # 获取乡镇数量
    total_townships_query = "SELECT COUNT(DISTINCT 乡镇级) as count FROM 广东省自然村"
    total_townships = execute_query(db, total_townships_query)[0]["count"]

    # 获取唯一字符数（从char_frequency_global表）
    unique_chars_query = """
        SELECT COUNT(DISTINCT char) as count
        FROM char_frequency_global
        WHERE run_id = (SELECT MAX(run_id) FROM char_frequency_global)
    """
    unique_chars_result = execute_query(db, unique_chars_query)
    unique_chars = unique_chars_result[0]["count"] if unique_chars_result else 0

    # 获取数据库大小
    db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024) if os.path.exists(DB_PATH) else 0

    # 获取最后更新时间（从数据库文件修改时间）
    last_updated = datetime.fromtimestamp(os.path.getmtime(DB_PATH)) if os.path.exists(DB_PATH) else datetime.now()

    return {
        "total_villages": total_villages,
        "total_cities": total_cities,
        "total_counties": total_counties,
        "total_townships": total_townships,
        "unique_characters": unique_chars,
        "database_size_mb": round(db_size_mb, 2),
        "last_updated": last_updated
    }


@router.get("/tables", response_model=List[TableInfo])
def get_table_info(db: sqlite3.Connection = Depends(get_db)):
    """
    获取数据库表信息
    Get database table information

    Returns:
        List[TableInfo]: 表信息列表
    """
    # 获取所有表名
    tables_query = """
        SELECT name as table_name
        FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """
    tables = execute_query(db, tables_query)

    table_info_list = []
    for table in tables:
        table_name = table["table_name"]

        # 获取行数
        count_query = f"SELECT COUNT(*) as count FROM `{table_name}`"
        try:
            row_count = execute_query(db, count_query)[0]["count"]
        except:
            row_count = 0

        # 估算表大小（SQLite没有直接的表大小查询，这里简化处理）
        # 实际大小需要通过VACUUM或其他方式获取
        size_mb = 0.0  # 简化处理，实际可以通过页数估算

        table_info_list.append({
            "table_name": table_name,
            "row_count": row_count,
            "size_mb": size_mb
        })

    return table_info_list
