"""
VillagesML 统计 API
Statistics API endpoints for VillagesML
"""
from fastapi import APIRouter, Depends
import sqlite3
from typing import Dict, Any

from ..dependencies import get_db

router = APIRouter(prefix="/statistics")


@router.get("/ngrams")
def get_ngram_statistics(db: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    """
    获取 N-gram 统计信息
    Get N-gram statistics

    Returns:
        dict: N-gram 统计数据
    """
    cursor = db.cursor()

    # 检查是否有 total_before_filter 字段
    cursor.execute("PRAGMA table_info(ngram_significance)")
    columns = [col[1] for col in cursor.fetchall()]
    has_total_before_filter = 'total_before_filter' in columns

    # 按级别统计，同时推导全局计数（避免额外的全表 COUNT 查询）
    by_level = {}
    total_significance = 0
    significant_count = 0
    total_before_filter_global = 0

    if has_total_before_filter:
        # 用 CTE 预聚合去重，消灭关联子查询
        cursor.execute("""
            WITH level_before AS (
                SELECT level, SUM(total_before_filter) AS total_before
                FROM (SELECT DISTINCT level, region, total_before_filter
                      FROM ngram_significance)
                GROUP BY level
            )
            SELECT ns.level,
                   COUNT(*) AS total,
                   SUM(CASE WHEN p_value < 0.05 THEN 1 ELSE 0 END) AS significant,
                   lb.total_before
            FROM ngram_significance ns
            JOIN level_before lb ON ns.level = lb.level
            GROUP BY ns.level
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
        cursor.execute("""
            SELECT level,
                   COUNT(*) AS total,
                   SUM(CASE WHEN p_value < 0.05 THEN 1 ELSE 0 END) AS significant
            FROM ngram_significance
            GROUP BY level
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
    cursor.execute("SELECT COUNT(*) FROM regional_ngram_frequency")
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


@router.get("/database")
def get_database_statistics(db: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    """
    获取数据库统计信息
    Get database statistics

    Returns:
        dict: 数据库统计数据
    """
    cursor = db.cursor()

    tables = [
        'regional_ngram_frequency',
        'ngram_tendency',
        'ngram_significance',
        'pattern_regional_analysis',
        'char_regional_analysis',
        'semantic_regional_analysis'
    ]

    table_stats = {}
    total_records = 0

    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            table_stats[table] = count
            total_records += count
        except:
            table_stats[table] = 0

    return {
        "tables": table_stats,
        "total_records": total_records,
        "note": "Total record count across major VillagesML tables"
    }
