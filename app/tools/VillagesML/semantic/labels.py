"""
语义标签API
Semantic Labels API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single
from ..config import DEFAULT_RUN_ID
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/semantic/labels", tags=["semantic"])


@router.get("/by-character")
def get_semantic_label_by_character(
    char: str = Query(..., description="字符", min_length=1, max_length=1),
    run_id: Optional[str] = Query(None, description="语义分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取字符的LLM生成语义标签
    Get LLM-generated semantic label for a character

    Args:
        char: 字符
        run_id: 语义分析运行ID

    Returns:
        dict: 语义标签信息
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic")

    query = """
        SELECT
            char as character,
            semantic_category,
            confidence,
            llm_explanation
        FROM semantic_labels
        WHERE run_id = ? AND char = ?
    """

    result = execute_single(db, query, (run_id, char))

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No semantic label found for character: {char}"
        )

    return result


@router.get("/by-category")
def get_characters_by_semantic_category(
    category: str = Query(..., description="语义类别"),
    run_id: Optional[str] = Query(None, description="语义分析运行ID（留空使用活跃版本）"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="最小置信度"),
    limit: int = Query(100, ge=1, le=500, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取指定语义类别的所有字符
    Get all characters in a specific semantic category

    Args:
        category: 语义类别
        run_id: 语义分析运行ID
        min_confidence: 最小置信度（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 字符列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic")

    query = """
        SELECT
            char as character,
            semantic_category,
            confidence,
            llm_explanation
        FROM semantic_labels
        WHERE run_id = ? AND semantic_category = ?
    """
    params = [run_id, category]

    # 现场过滤：最小置信度
    if min_confidence is not None:
        query += " AND confidence >= ?"
        params.append(min_confidence)

    query += " ORDER BY confidence DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No characters found for category: {category}"
        )

    return results


@router.get("/categories")
def list_semantic_categories(
    run_id: Optional[str] = Query(None, description="语义分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    列出所有语义类别及其字符数量
    List all semantic categories with character counts

    Args:
        run_id: 语义分析运行ID

    Returns:
        List[dict]: 类别统计列表
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("semantic")

    query = """
        SELECT
            semantic_category,
            COUNT(*) as character_count,
            AVG(confidence) as avg_confidence
        FROM semantic_labels
        WHERE run_id = ?
        GROUP BY semantic_category
        ORDER BY character_count DESC
    """

    results = execute_query(db, query, (run_id,))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No semantic categories found for run_id: {run_id}"
        )

    return results
