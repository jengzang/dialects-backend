"""
语义标签API
Semantic Labels API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single

router = APIRouter(prefix="/semantic/labels", tags=["semantic"])


@router.get("/by-character")
def get_semantic_label_by_character(
    char: str = Query(..., description="字符", min_length=1, max_length=1),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取字符的LLM生成语义标签
    Get LLM-generated semantic label for a character

    Args:
        char: 字符

    Returns:
        dict: 语义标签信息
    """
    try:
        query = """
            SELECT
                char as character,
                semantic_category,
                confidence,
                llm_explanation
            FROM semantic_labels
            WHERE char = ?
        """

        result = execute_single(db, query, (char,))

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No semantic label found for character: {char}"
            )

        return result
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            raise HTTPException(
                status_code=503,
                detail="Semantic labels feature is not available. The semantic_labels table has not been created yet."
            )
        raise


@router.get("/by-category")
def get_characters_by_semantic_category(
    category: str = Query(..., description="语义类别"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="最小置信度"),
    limit: int = Query(100, ge=1, le=500, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取指定语义类别的所有字符
    Get all characters in a specific semantic category

    Args:
        category: 语义类别
        min_confidence: 最小置信度（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 字符列表
    """
    try:
        query = """
            SELECT
                char as character,
                semantic_category,
                confidence,
                llm_explanation
            FROM semantic_labels
            WHERE semantic_category = ?
        """
        params = [category]

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
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            raise HTTPException(
                status_code=503,
                detail="Semantic labels feature is not available. The semantic_labels table has not been created yet."
            )
        raise


@router.get("/categories")
def list_semantic_categories(
    db: sqlite3.Connection = Depends(get_db)
):
    """
    列出所有语义类别及其字符数量
    List all semantic categories with character counts

    Returns:
        List[dict]: 类别统计列表
    """
    try:
        query = """
            SELECT
                semantic_category,
                COUNT(*) as character_count,
                AVG(confidence) as avg_confidence
            FROM semantic_labels
            GROUP BY semantic_category
            ORDER BY character_count DESC
        """

        results = execute_query(db, query)

        if not results:
            raise HTTPException(
                status_code=503,
                detail="Semantic labels feature is not available. The semantic_labels table does not exist in the database."
            )

        return results
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            raise HTTPException(
                status_code=503,
                detail="Semantic labels feature is not available. The semantic_labels table has not been created yet."
            )
        raise
