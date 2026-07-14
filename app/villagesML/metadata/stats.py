"""
元数据统计API
Metadata Statistics API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from typing import List, Optional
import sqlite3
import os
from datetime import datetime

from ..dependencies import get_db_connection, get_dbpath, execute_query
from ..schema_runtime import qcolumn, qtable, quote_identifier, resolve_db_path
from ..schema_keys import C, T
from ..models import SystemOverview, TableInfo, RegionInfo, TableColumn
from ..cache_utils import api_cache

router = APIRouter(prefix="/metadata/stats")


def _get_system_overview_sync(dbpath: str):
    """
    同步获取系统概览统计（在线程池中执行）
    Synchronous function to get system overview (runs in thread pool)
    """
    db_file = resolve_db_path(dbpath)
    with get_db_connection(dbpath) as db:
        villages_table = qtable(dbpath, T.VILLAGES)
        villages_city = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.CITY)
        villages_county = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COUNTY)
        villages_township = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.TOWNSHIP)
        char_frequency_table = qtable(dbpath, T.CHAR_FREQUENCY_GLOBAL)

        # 获取村庄总数（使用预处理表）
        total_villages_query = f"SELECT COUNT(*) as count FROM {villages_table}"
        total_villages = execute_query(db, total_villages_query)[0]["count"]

        # 获取城市数量（使用预处理表）
        total_cities_query = f"SELECT COUNT(DISTINCT {villages_city}) as count FROM {villages_table}"
        total_cities = execute_query(db, total_cities_query)[0]["count"]

        # 获取区县数量（使用预处理表）
        total_counties_query = f"SELECT COUNT(DISTINCT {villages_county}) as count FROM {villages_table}"
        total_counties = execute_query(db, total_counties_query)[0]["count"]

        # 获取乡镇数量（使用预处理表）
        total_townships_query = f"SELECT COUNT(DISTINCT {villages_township}) as count FROM {villages_table}"
        total_townships = execute_query(db, total_townships_query)[0]["count"]

        # 获取唯一字符数（从char_frequency_global表）
        unique_chars_query = f"""
            SELECT COUNT(DISTINCT char) as count
            FROM {char_frequency_table}
        """
        unique_chars_result = execute_query(db, unique_chars_query)
        unique_chars = unique_chars_result[0]["count"] if unique_chars_result else 0

        # 获取数据库大小
        db_size_mb = os.path.getsize(db_file) / (1024 * 1024) if os.path.exists(db_file) else 0

        # 获取最后更新时间（从数据库文件修改时间）
        last_updated = datetime.fromtimestamp(os.path.getmtime(db_file)) if os.path.exists(db_file) else datetime.now()

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
async def get_system_overview(dbpath: str = Depends(get_dbpath)):
    """
    获取系统概览统计
    Get system overview statistics

    Returns:
        SystemOverview: 系统概览信息
    """
    return await run_in_threadpool(_get_system_overview_sync, dbpath)


def _get_table_info_sync(dbpath: str):
    """
    同步获取数据库表信息（在线程池中执行）
    Synchronous function to get table info (runs in thread pool)
    """
    db_file = resolve_db_path(dbpath)
    with get_db_connection(dbpath) as db:
        sqlite_master_table = qtable(dbpath, T.SQLITE_MASTER)
        sqlite_master_name = qcolumn(dbpath, T.SQLITE_MASTER, C.SQLITE_MASTER.NAME)
        sqlite_master_table_name = qcolumn(dbpath, T.SQLITE_MASTER, C.SQLITE_MASTER.TABLE_NAME)
        sqlite_master_type = qcolumn(dbpath, T.SQLITE_MASTER, C.SQLITE_MASTER.TYPE)
        sqlite_stat1_table = qtable(dbpath, T.SQLITE_STAT1)
        sqlite_stat1_table_name = qcolumn(dbpath, T.SQLITE_STAT1, C.SQLITE_STAT1.TABLE_NAME)
        sqlite_stat1_stat = qcolumn(dbpath, T.SQLITE_STAT1, C.SQLITE_STAT1.STAT)
        dbstat_table = qtable(dbpath, T.DBSTAT)
        dbstat_name = qcolumn(dbpath, T.DBSTAT, C.DBSTAT.NAME)
        dbstat_page_size = qcolumn(dbpath, T.DBSTAT, C.DBSTAT.PAGE_SIZE)

        # 获取所有表名
        tables_query = f"""
            SELECT {sqlite_master_name} as table_name
            FROM {sqlite_master_table}
            WHERE {sqlite_master_type}='table' AND {sqlite_master_name} NOT LIKE 'sqlite_%'
            ORDER BY {sqlite_master_name}
        """
        tables = execute_query(db, tables_query)

        # 尝试从 sqlite_stat1 获取行数估算（避免 COUNT(*) 全表扫描）
        stat1_available = False
        stat1_data = {}
        try:
            stat1_query = f"SELECT {sqlite_stat1_table_name} as tbl, {sqlite_stat1_stat} as stat FROM {sqlite_stat1_table}"
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

        # 一次性获取所有表和索引的 dbstat 数据，避免逐表扫描 dbstat
        dbstat_sizes = {}
        dbstat_available = False
        try:
            dbstat_query = f"SELECT {dbstat_name} as name, COALESCE(SUM({dbstat_page_size}), 0) AS bytes FROM {dbstat_table} GROUP BY {dbstat_name}"
            for row in execute_query(db, dbstat_query):
                dbstat_sizes[row["name"]] = row["bytes"]
            dbstat_available = True
        except Exception:
            dbstat_available = False

        # 一次性获取所有索引名及其所属表
        index_tbl_map = {}
        try:
            idx_rows = execute_query(
                db,
                f"""
                SELECT {sqlite_master_name} as name, {sqlite_master_table_name} as tbl_name
                FROM {sqlite_master_table}
                WHERE {sqlite_master_type}='index' AND {sqlite_master_name} NOT LIKE 'sqlite_%'
                """,
            )
            for row in idx_rows:
                index_tbl_map[row["name"]] = row["tbl_name"]
        except Exception:
            pass

        table_info_list = []
        for table in tables:
            table_name = table["table_name"]

            # 获取行数（优先使用 sqlite_stat1 估算）
            if stat1_available and table_name in stat1_data:
                row_count = stat1_data[table_name]
            else:
                # Fallback: 使用 COUNT(*) （仅当 stat1 不可用时）
                count_query = f"SELECT COUNT(*) as count FROM {quote_identifier(table_name)}"
                try:
                    row_count = execute_query(db, count_query)[0]["count"]
                except:
                    row_count = 0

            # 获取表数据大小：从批量 dbstat 结果中取
            if dbstat_available:
                data_bytes = dbstat_sizes.get(table_name, 0)
                data_size_mb = data_bytes / (1024 * 1024)
            else:
                data_size_mb = (row_count * 100) / (1024 * 1024) if row_count > 0 else 0.0

            # 获取表关联的所有索引大小
            if dbstat_available:
                index_bytes = sum(
                    dbstat_sizes.get(iname, 0)
                    for iname, tname in index_tbl_map.items() if tname == table_name
                )
                index_size_mb = index_bytes / (1024 * 1024)
            else:
                index_size_mb = 0.0

            total_size_mb = data_size_mb + index_size_mb
            size_mb = total_size_mb

            # 获取索引信息
            index_query = f"""
                SELECT COUNT(*) as count
                FROM {sqlite_master_table}
                WHERE {sqlite_master_type}='index' AND {sqlite_master_table_name} = ? AND {sqlite_master_name} NOT LIKE 'sqlite_%'
            """
            try:
                index_count = execute_query(db, index_query, (table_name,))[0]["count"]
            except:
                index_count = 0

            # 获取列信息
            columns = []
            try:
                # 获取列定义
                pragma_query = f"PRAGMA table_info({quote_identifier(table_name)})"
                column_info = execute_query(db, pragma_query)

                # 获取所有索引
                index_list_query = f"""
                    SELECT {sqlite_master_name} as name FROM {sqlite_master_table}
                    WHERE {sqlite_master_type}='index' AND {sqlite_master_table_name} = ? AND {sqlite_master_name} NOT LIKE 'sqlite_%'
                """
                indexes = execute_query(db, index_list_query, (table_name,))

                # 对每个索引，获取其包含的列
                indexed_columns = set()
                for idx in indexes:
                    idx_name = idx["name"]
                    idx_info_query = f"PRAGMA index_info({quote_identifier(idx_name)})"
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
                if os.path.exists(db_file):
                    mtime = os.path.getmtime(db_file)
                    last_modified = datetime.fromtimestamp(mtime).isoformat()
                else:
                    last_modified = None
            except:
                last_modified = None

            table_info_list.append({
                "table_name": table_name,
                "row_count": row_count,
                "size_mb": round(size_mb, 2),
                "data_size_mb": round(data_size_mb, 2),
                "index_size_mb": round(index_size_mb, 2),
                "index_count": index_count,
                "last_modified": last_modified,
                "columns": columns
            })

        return table_info_list


@router.get("/tables", response_model=List[TableInfo])
@api_cache(ttl=300, prefix="metadata_tables")
async def get_table_info(dbpath: str = Depends(get_dbpath)):
    """
    获取数据库表信息
    Get database table information

    Returns:
        List[TableInfo]: 表信息列表
    """
    return await run_in_threadpool(_get_table_info_sync, dbpath)


def _get_regions_sync(dbpath: str, level: str, parent: Optional[str] = None):
    """
    同步获取区域列表（在线程池中执行）
    Synchronous function to get region list (runs in thread pool)

    Args:
        level: 区域级别 ('city', 'county', 'township')
        parent: 父区域名称（可选）

    Returns:
        List[dict]: 区域信息列表（包含完整层级信息）
    """
    villages_table = qtable(dbpath, T.VILLAGES)
    villages_city = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.CITY)
    villages_county = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COUNTY)
    villages_township = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.TOWNSHIP)

    # 映射级别到数据库列名
    level_column_map = {
        'city': villages_city,
        'county': villages_county,
        'township': villages_township
    }

    # 映射父级别到列名
    parent_column_map = {
        'county': villages_city,  # county的父级是city
        'township': villages_county  # township的父级是county
    }

    if level not in level_column_map:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid level: {level}. Must be one of: city, county, township"
        )

    level_column = level_column_map[level]

    with get_db_connection(dbpath) as db:
        # 根据 level 构建不同的查询
        if level == 'city':
            # 城市级别：只返回城市，county 和 township 为 NULL
            if parent is not None:
                raise HTTPException(
                    status_code=422,
                    detail="City level does not support parent parameter"
                )

            query = f"""
                SELECT
                    {villages_city} as city,
                    NULL as county,
                    NULL as township,
                    {villages_city} as name,
                    'city' as level,
                    COUNT(*) as village_count
                FROM {villages_table}
                WHERE {villages_city} IS NOT NULL AND {villages_city} != ''
                GROUP BY {villages_city}
                ORDER BY {villages_city}
            """
            results = execute_query(db, query)

        elif level == 'county':
            # 县区级别：返回城市和县区，township 为 NULL
            if parent is None:
                query = f"""
                    SELECT
                        {villages_city} as city,
                        {villages_county} as county,
                        NULL as township,
                        {villages_county} as name,
                        'county' as level,
                        COUNT(*) as village_count
                    FROM {villages_table}
                    WHERE {villages_county} IS NOT NULL AND {villages_county} != ''
                    GROUP BY {villages_city}, {villages_county}
                    ORDER BY {villages_city}, {villages_county}
                """
                results = execute_query(db, query)
            else:
                # 有父级过滤（按城市过滤）
                query = f"""
                    SELECT
                        {villages_city} as city,
                        {villages_county} as county,
                        NULL as township,
                        {villages_county} as name,
                        'county' as level,
                        COUNT(*) as village_count
                    FROM {villages_table}
                    WHERE {villages_city} = ?
                        AND {villages_county} IS NOT NULL
                        AND {villages_county} != ''
                    GROUP BY {villages_city}, {villages_county}
                    ORDER BY {villages_city}, {villages_county}
                """
                results = execute_query(db, query, (parent,))

        else:  # level == 'township'
            # 乡镇级别：返回完整的层级信息
            if parent is None:
                query = f"""
                    SELECT
                        {villages_city} as city,
                        {villages_county} as county,
                        {villages_township} as township,
                        {villages_township} as name,
                        'township' as level,
                        COUNT(*) as village_count
                    FROM {villages_table}
                    WHERE {villages_township} IS NOT NULL AND {villages_township} != ''
                    GROUP BY {villages_city}, {villages_county}, {villages_township}
                    ORDER BY {villages_city}, {villages_county}, {villages_township}
                """
                results = execute_query(db, query)
            else:
                # 有父级过滤（按县区过滤）
                query = f"""
                    SELECT
                        {villages_city} as city,
                        {villages_county} as county,
                        {villages_township} as township,
                        {villages_township} as name,
                        'township' as level,
                        COUNT(*) as village_count
                    FROM {villages_table}
                    WHERE {villages_county} = ?
                        AND {villages_township} IS NOT NULL
                        AND {villages_township} != ''
                    GROUP BY {villages_city}, {villages_county}, {villages_township}
                    ORDER BY {villages_city}, {villages_county}, {villages_township}
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
    parent: Optional[str] = None,
    dbpath: str = Depends(get_dbpath),
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
    return await run_in_threadpool(_get_regions_sync, dbpath, level, parent)
