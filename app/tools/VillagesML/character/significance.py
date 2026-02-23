"""
字符显著性API
Character Significance API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query
from ..config import DEFAULT_RUN_ID
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/character/significance", tags=["character"])


@router.get("/by-character")
def get_character_significance(
    char: str = Query(..., description="字符", min_length=1, max_length=1),
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    region_level: str = Query("city", description="区域级别", pattern="^(city|county|township)$"),
    min_zscore: Optional[float] = Query(None, description="最小Z分数阈值"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取字符在各区域的统计显著性
    Get statistical significance of a character across regions

    Args:
        char: 字符
        run_id: 分析运行ID
        region_level: 区域级别
        min_zscore: 最小Z分数阈值（可选）

    Returns:
        List[dict]: 区域显著性列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("char_significance")

    query = """
        SELECT
            region_name,
            chi_square_statistic,
            p_value,
            is_significant,
            effect_size
        FROM tendency_significance
        WHERE run_id = ? AND char = ? AND region_level = ?
    """
    params = [run_id, char, region_level]

    # 现场过滤：最小Z分数
    if min_zscore is not None:
        query += " AND ABS(chi_square_statistic) >= ?"
        params.append(abs(min_zscore))

    query += " ORDER BY ABS(chi_square_statistic) DESC"

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No significance data found for character: {char}"
        )

    return results


@router.get("/by-region")
def get_significant_characters_by_region(
    region_name: str = Query(..., description="区域名称"),
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    region_level: str = Query("city", description="区域级别", pattern="^(city|county|township)$"),
    significance_only: bool = Query(True, description="仅返回显著字符"),
    top_k: int = Query(20, ge=1, le=100, description="返回前K个字符"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取指定区域的显著字符
    Get significant characters for a specific region

    Args:
        region_name: 区域名称
        run_id: 分析运行ID
        region_level: 区域级别
        significance_only: 仅返回显著字符（p < 0.05）
        top_k: 返回前K个字符

    Returns:
        List[dict]: 显著字符列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("char_significance")

    query = """
        SELECT
            char as character,
            chi_square_statistic,
            p_value,
            is_significant,
            effect_size
        FROM tendency_significance
        WHERE run_id = ? AND region_name = ? AND region_level = ?
    """
    params = [run_id, region_name, region_level]

    # 现场过滤：仅显著字符
    if significance_only:
        query += " AND is_significant = 1"

    query += " ORDER BY ABS(chi_square_statistic) DESC LIMIT ?"
    params.append(top_k)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No significant characters found for region: {region_name}"
        )

    return results


@router.get("/summary")
def get_significance_summary(
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    region_level: str = Query("city", description="区域级别", pattern="^(city|county|township)$"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取显著性分析汇总统计
    Get significance analysis summary statistics

    Args:
        run_id: 分析运行ID
        region_level: 区域级别

    Returns:
        dict: 汇总统计信息
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("char_significance")

    query = """
        SELECT
            COUNT(DISTINCT char) as total_characters,
            COUNT(DISTINCT region_name) as total_regions,
            SUM(CASE WHEN is_significant = 1 THEN 1 ELSE 0 END) as significant_count,
            AVG(ABS(chi_square_statistic)) as avg_abs_chi_square,
            MAX(ABS(chi_square_statistic)) as max_abs_chi_square
        FROM tendency_significance
        WHERE run_id = ? AND region_level = ?
    """

    result = execute_query(db, query, (run_id, region_level))

    if not result or len(result) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No significance data found for run_id: {run_id}"
        )

    return result[0]
