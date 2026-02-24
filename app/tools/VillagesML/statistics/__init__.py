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

    # 按级别统计
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

    return {
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
