"""
元数据统计API
Metadata Statistics API endpoints
"""
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from typing import List, Optional
import sqlite3
import os
from datetime import datetime

from ..dependencies import get_db_connection, execute_query
from ..config import DB_PATH
from ..models import SystemOverview, TableInfo, RegionInfo, TableColumn
from ..cache_utils import api_cache

router = APIRouter(prefix="/metadata/stats")


def _get_system_overview_sync():
    """
    同步获取系统概览统计（在线程池中执行）
    Synchronous function to get system overview (runs in thread pool)
    """
    with get_db_connection() as db:
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


@router.get("/overview", response_model=SystemOverview)
async def get_system_overview():
    """
    获取系统概览统计
    Get system overview statistics

    Returns:
        SystemOverview: 系统概览信息
    """
    return await run_in_threadpool(_get_system_overview_sync)


def _get_table_info_sync():
    """
    同步获取数据库表信息（在线程池中执行）
    Synchronous function to get table info (runs in thread pool)
    """
    with get_db_connection() as db:
        # 获取所有表名
        tables_query = """
            SELECT name as table_name
            FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """
        tables = execute_query(db, tables_query)

        # 获取数据库页大小
        page_size_query = "PRAGMA page_size"
        page_size = execute_query(db, page_size_query)[0]["page_size"]

        # 尝试从 sqlite_stat1 获取行数估算（避免 COUNT(*) 全表扫描）
        stat1_available = False
        stat1_data = {}
        try:
            stat1_query = "SELECT tbl, stat FROM sqlite_stat1"
            stat1_results = execute_query(db, stat1_query)
            stat1_available = True

            # 解析 stat 字段（格式: "row_count avg_row_size ..."）
            for row in stat1_results:
                tbl = row["tbl"]
                stat = row["stat"]
                if stat:
                    parts = stat.split()
                    if parts:
                        try:
                            row_count = int(parts[0])
                            stat1_data[tbl] = row_count
                        except:
                            pass
        except:
            # sqlite_stat1 不存在或未运行 ANALYZE
            pass

        table_info_list = []
        for table in tables:
            table_name = table["table_name"]

            # 获取行数（优先使用 sqlite_stat1 估算）
            if stat1_available and table_name in stat1_data:
                row_count = stat1_data[table_name]
            else:
                # Fallback: 使用 COUNT(*) （仅当 stat1 不可用时）
                count_query = f"SELECT COUNT(*) as count FROM `{table_name}`"
                try:
                    row_count = execute_query(db, count_query)[0]["count"]
                except:
                    row_count = 0

            # 获取表大小（估算方法：行数 * 平均行大小）
            # SQLite 没有直接的表大小查询，这里使用估算
            try:
                # 尝试使用 dbstat（如果可用）
                page_count_query = f"SELECT SUM(pageno) as pages FROM dbstat WHERE name = ?"
                page_result = execute_query(db, page_count_query, (table_name,))
                if page_result and page_result[0]["pages"]:
                    page_count = page_result[0]["pages"]
                    size_mb = (page_count * page_size) / (1024 * 1024)
                else:
                    # dbstat 不可用，使用粗略估算
                    # 假设每行平均 100 字节
                    size_mb = (row_count * 100) / (1024 * 1024)
            except:
                # 如果 dbstat 不可用，使用粗略估算
                # 假设每行平均 100 字节
                size_mb = (row_count * 100) / (1024 * 1024) if row_count > 0 else 0.0

            # 获取索引信息
            index_query = f"""
                SELECT COUNT(*) as count
                FROM sqlite_master
                WHERE type='index' AND tbl_name = ? AND name NOT LIKE 'sqlite_%'
            """
            try:
                index_count = execute_query(db, index_query, (table_name,))[0]["count"]
            except:
                index_count = 0

            # 获取列信息
            columns = []
            try:
                # 获取列定义
                pragma_query = f"PRAGMA table_info(`{table_name}`)"
                column_info = execute_query(db, pragma_query)

                # 获取所有索引
                index_list_query = f"""
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND tbl_name = ? AND name NOT LIKE 'sqlite_%'
                """
                indexes = execute_query(db, index_list_query, (table_name,))

                # 对每个索引，获取其包含的列
                indexed_columns = set()
                for idx in indexes:
                    idx_name = idx["name"]
                    idx_info_query = f"PRAGMA index_info(`{idx_name}`)"
                    idx_cols = execute_query(db, idx_info_query)
                    for col in idx_cols:
                        indexed_columns.add(col["name"])

                # 构建列信息
                for col in column_info:
                    columns.append({
                        "name": col["name"],
                        "type": col["type"],
                        "not_null": bool(col["notnull"]),
                        "has_index": col["name"] in indexed_columns
                    })
            except:
                columns = []

            # 获取最后修改时间（SQLite 没有直接的表修改时间，使用数据库文件时间）
            try:
                import os
                from datetime import datetime
                if os.path.exists(DB_PATH):
                    mtime = os.path.getmtime(DB_PATH)
                    last_modified = datetime.fromtimestamp(mtime).isoformat()
                else:
                    last_modified = None
            except:
                last_modified = None

            table_info_list.append({
                "table_name": table_name,
                "row_count": row_count,
                "size_mb": round(size_mb, 2),
                "index_count": index_count,
                "last_modified": last_modified,
                "columns": columns
            })

        return table_info_list


@router.get("/tables", response_model=List[TableInfo])
@api_cache(ttl=300, prefix="metadata_tables")
async def get_table_info():
    """
    获取数据库表信息
    Get database table information

    Returns:
        List[TableInfo]: 表信息列表
    """
    return await run_in_threadpool(_get_table_info_sync)


def _get_regions_sync(level: str, parent: Optional[str] = None):
    """
    同步获取区域列表（在线程池中执行）
    Synchronous function to get region list (runs in thread pool)

    Args:
        level: 区域级别 ('city', 'county', 'township')
        parent: 父区域名称（可选）

    Returns:
        List[dict]: 区域信息列表（包含完整层级信息）
    """
    # 映射级别到数据库列名
    level_column_map = {
        'city': '市级',
        'county': '区县级',
        'township': '乡镇级'
    }

    # 映射父级别到列名
    parent_column_map = {
        'county': '市级',  # county的父级是city
        'township': '区县级'  # township的父级是county
    }

    if level not in level_column_map:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid level: {level}. Must be one of: city, county, township"
        )

    level_column = level_column_map[level]

    with get_db_connection() as db:
        # 根据 level 构建不同的查询
        if level == 'city':
            # 城市级别：只返回城市，county 和 township 为 NULL
            if parent is not None:
                raise HTTPException(
                    status_code=422,
                    detail="City level does not support parent parameter"
                )

            query = """
                SELECT
                    市级 as city,
                    NULL as county,
                    NULL as township,
                    市级 as name,
                    'city' as level,
                    COUNT(*) as village_count
                FROM 广东省自然村
                WHERE 市级 IS NOT NULL AND 市级 != ''
                GROUP BY 市级
                ORDER BY 市级
            """
            results = execute_query(db, query)

        elif level == 'county':
            # 县区级别：返回城市和县区，township 为 NULL
            if parent is None:
                query = """
                    SELECT
                        市级 as city,
                        区县级 as county,
                        NULL as township,
                        区县级 as name,
                        'county' as level,
                        COUNT(*) as village_count
                    FROM 广东省自然村
                    WHERE 区县级 IS NOT NULL AND 区县级 != ''
                    GROUP BY 市级, 区县级
                    ORDER BY 市级, 区县级
                """
                results = execute_query(db, query)
            else:
                # 有父级过滤（按城市过滤）
                query = """
                    SELECT
                        市级 as city,
                        区县级 as county,
                        NULL as township,
                        区县级 as name,
                        'county' as level,
                        COUNT(*) as village_count
                    FROM 广东省自然村
                    WHERE 市级 = ?
                        AND 区县级 IS NOT NULL
                        AND 区县级 != ''
                    GROUP BY 市级, 区县级
                    ORDER BY 市级, 区县级
                """
                results = execute_query(db, query, (parent,))

        else:  # level == 'township'
            # 乡镇级别：返回完整的层级信息
            if parent is None:
                query = """
                    SELECT
                        市级 as city,
                        区县级 as county,
                        乡镇级 as township,
                        乡镇级 as name,
                        'township' as level,
                        COUNT(*) as village_count
                    FROM 广东省自然村
                    WHERE 乡镇级 IS NOT NULL AND 乡镇级 != ''
                    GROUP BY 市级, 区县级, 乡镇级
                    ORDER BY 市级, 区县级, 乡镇级
                """
                results = execute_query(db, query)
            else:
                # 有父级过滤（按县区过滤）
                query = """
                    SELECT
                        市级 as city,
                        区县级 as county,
                        乡镇级 as township,
                        乡镇级 as name,
                        'township' as level,
                        COUNT(*) as village_count
                    FROM 广东省自然村
                    WHERE 区县级 = ?
                        AND 乡镇级 IS NOT NULL
                        AND 乡镇级 != ''
                    GROUP BY 市级, 区县级, 乡镇级
                    ORDER BY 市级, 区县级, 乡镇级
                """
                results = execute_query(db, query, (parent,))

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No regions found for level={level}" + (f", parent={parent}" if parent else "")
            )

        return results


@router.get("/regions", response_model=List[RegionInfo])
async def get_regions(
    level: str,
    parent: Optional[str] = None
):
    """
    获取区域列表
    Get list of regions at specified level

    Args:
        level: 区域级别 ('city', 'county', 'township')
        parent: 父区域名称（可选，用于层级过滤）
            - level=county时，parent为城市名称
            - level=township时，parent为县区名称

    Returns:
        List[RegionInfo]: 区域信息列表

    Examples:
        - GET /metadata/stats/regions?level=city
          返回所有城市
        - GET /metadata/stats/regions?level=county&parent=广州市
          返回广州市下的所有县区
        - GET /metadata/stats/regions?level=township&parent=番禺区
          返回番禺区下的所有乡镇
    """
    return await run_in_threadpool(_get_regions_sync, level, parent)
