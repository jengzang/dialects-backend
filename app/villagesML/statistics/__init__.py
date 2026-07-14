"""
villagesML 统计 API
Statistics API endpoints for villagesML
"""
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
import sqlite3
from typing import Dict, Any

from ..dependencies import get_db, get_dbpath
from ..cache_utils import api_cache
from ..schema_runtime import column_name, configured_table_list, qcolumn, qtable, table_name
from ..schema_keys import C, T, TABLE_LISTS

router = APIRouter(prefix="/statistics")


def _get_ngram_statistics_sync(db: sqlite3.Connection, dbpath: str) -> Dict[str, Any]:
    """
    同步获取 N-gram 统计信息（在线程池中执行）
    Synchronous function to get N-gram statistics (runs in thread pool)

    Args:
        db: 数据库连接

    Returns:
        dict: N-gram 统计数据
    """
    cursor = db.cursor()
    significance_table = qtable(dbpath, T.NGRAM_SIGNIFICANCE)
    significance_level = qcolumn(dbpath, T.NGRAM_SIGNIFICANCE, C.NGRAM_SIGNIFICANCE.LEVEL)
    significance_region = qcolumn(dbpath, T.NGRAM_SIGNIFICANCE, C.NGRAM_SIGNIFICANCE.REGION)
    significance_p_value = qcolumn(dbpath, T.NGRAM_SIGNIFICANCE, C.NGRAM_SIGNIFICANCE.P_VALUE)
    significance_total_before = qcolumn(dbpath, T.NGRAM_SIGNIFICANCE, C.NGRAM_SIGNIFICANCE.TOTAL_BEFORE_FILTER)
    regional_frequency_table = qtable(dbpath, T.REGIONAL_NGRAM_FREQUENCY)

    # 检查是否有 total_before_filter 字段
    cursor.execute(f"PRAGMA table_info({significance_table})")
    columns = [col[1] for col in cursor.fetchall()]
    has_total_before_filter = column_name(dbpath, T.NGRAM_SIGNIFICANCE, C.NGRAM_SIGNIFICANCE.TOTAL_BEFORE_FILTER) in columns

    # 按级别统计，同时推导全局计数（避免额外的全表 COUNT 查询）
    by_level = {}
    total_significance = 0
    significant_count = 0
    total_before_filter_global = 0

    if has_total_before_filter:
        # 用 CTE 预聚合去重，消灭关联子查询
        cursor.execute(f"""
            WITH level_before AS (
                SELECT {significance_level} as level, SUM({significance_total_before}) AS total_before
                FROM (SELECT DISTINCT {significance_level}, {significance_region}, {significance_total_before}
                      FROM {significance_table})
                GROUP BY {significance_level}
            )
            SELECT ns.{significance_level} as level,
                   COUNT(*) AS total,
                   SUM(CASE WHEN ns.{significance_p_value} < 0.05 THEN 1 ELSE 0 END) AS significant,
                   lb.total_before
            FROM {significance_table} ns
            JOIN level_before lb ON ns.{significance_level} = lb.level
            GROUP BY ns.{significance_level}
        """)
        for level, total, sig, total_before in cursor.fetchall():
            total_before = total_before or total
            by_level[level] = {
                "total": total,
                "significant": sig,
                "total_before_filter": total_before,
                "significant_rate": round(sig / total_before * 100, 1) if total_before > 0 else 0
            }
            total_significance += total
            significant_count += sig
            total_before_filter_global += total_before
    else:
        cursor.execute(f"""
            SELECT {significance_level} as level,
                   COUNT(*) AS total,
                   SUM(CASE WHEN {significance_p_value} < 0.05 THEN 1 ELSE 0 END) AS significant
            FROM {significance_table}
            GROUP BY {significance_level}
        """)
        for level, total, sig in cursor.fetchall():
            by_level[level] = {
                "total": total,
                "significant": sig,
                "significant_rate": round(sig / total * 100, 1) if total > 0 else 0
            }
            total_significance += total
            significant_count += sig
        total_before_filter_global = None

    # 统计 regional_ngram_frequency 表
    cursor.execute(f"SELECT COUNT(*) FROM {regional_frequency_table}")
    regional_total = cursor.fetchone()[0]

    result = {
        "ngram_significance": {
            "total": total_significance,
            "significant": significant_count,
            "insignificant": total_significance - significant_count,
            "significant_rate": round(significant_count / total_significance * 100, 1) if total_significance > 0 else 0
        },
        "by_level": by_level,
        "regional_ngram_frequency": {
            "total": regional_total
        },
        "note": "Statistics based on current database state. After optimization, only significant n-grams (p < 0.05) will be retained."
    }

    # 如果有原始总数，添加到结果中
    if has_total_before_filter and total_before_filter_global:
        result["ngram_significance"]["total_before_filter"] = total_before_filter_global
        result["ngram_significance"]["filter_rate"] = round((total_before_filter_global - total_significance) / total_before_filter_global * 100, 1)

    return result


@router.get("/ngrams")
@api_cache(ttl=300, prefix="ngrams_stats")
async def get_ngram_statistics(
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
) -> Dict[str, Any]:
    """
    获取 N-gram 统计信息
    Get N-gram statistics

    Returns:
        dict: N-gram 统计数据
    """
    return await run_in_threadpool(_get_ngram_statistics_sync, db, dbpath)


@router.get("/database")
def get_database_statistics(
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
) -> Dict[str, Any]:
    """
    获取数据库统计信息
    Get database statistics

    Returns:
        dict: 数据库统计数据
    """
    cursor = db.cursor()

    table_stats = {}
    total_records = 0

    for logical_table in configured_table_list(dbpath, TABLE_LISTS.DATABASE_STATISTICS):
        response_key = table_name(dbpath, logical_table)
        table = qtable(dbpath, logical_table)
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            table_stats[response_key] = count
            total_records += count
        except:
            table_stats[response_key] = 0

    return {
        "tables": table_stats,
        "total_records": total_records,
        "note": "Total record count across major villagesML tables"
    }
