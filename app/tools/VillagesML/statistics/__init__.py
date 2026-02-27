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

    # 统计 ngram_significance 表
    cursor.execute("SELECT COUNT(*) FROM ngram_significance")
    total_significance = cursor.fetchone()[0]

    # 统计显著 N-gram
    cursor.execute("SELECT COUNT(*) FROM ngram_significance WHERE p_value < 0.05")
    significant_count = cursor.fetchone()[0]

    # 检查是否有 total_before_filter 字段
    cursor.execute("PRAGMA table_info(ngram_significance)")
    columns = [col[1] for col in cursor.fetchall()]
    has_total_before_filter = 'total_before_filter' in columns

    # 按级别统计
    if has_total_before_filter:
        # 有原始总数字段：统计清理前后的数量
        cursor.execute("""
            SELECT level,
                   COUNT(*) as total,
                   SUM(CASE WHEN p_value < 0.05 THEN 1 ELSE 0 END) as significant,
                   (SELECT SUM(total_before_filter)
                    FROM (SELECT DISTINCT level as l, region, total_before_filter
                          FROM ngram_significance WHERE level = ns.level)) as total_before
            FROM ngram_significance ns
            GROUP BY level
        """)

        by_level = {}
        for row in cursor.fetchall():
            level, total, sig, total_before = row
            by_level[level] = {
                "total": total,
                "significant": sig,
                "total_before_filter": total_before if total_before else total,
                "significant_rate": round(sig / total_before * 100, 1) if total_before and total_before > 0 else 0
            }
    else:
        # 没有原始总数字段：使用当前数据
        cursor.execute("""
            SELECT level,
                   COUNT(*) as total,
                   SUM(CASE WHEN p_value < 0.05 THEN 1 ELSE 0 END) as significant
            FROM ngram_significance
            GROUP BY level
        """)

        by_level = {}
        for row in cursor.fetchall():
            level, total, sig = row
            by_level[level] = {
                "total": total,
                "significant": sig,
                "significant_rate": round(sig / total * 100, 1) if total > 0 else 0
            }

    # 统计 regional_ngram_frequency 表
    cursor.execute("SELECT COUNT(*) FROM regional_ngram_frequency")
    regional_total = cursor.fetchone()[0]

    # 计算全局的原始总数（如果有字段）
    if has_total_before_filter:
        cursor.execute("""
            SELECT SUM(total_before_filter)
            FROM (SELECT DISTINCT level, region, total_before_filter
                  FROM ngram_significance)
        """)
        total_before_filter_global = cursor.fetchone()[0]
    else:
        total_before_filter_global = None

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
