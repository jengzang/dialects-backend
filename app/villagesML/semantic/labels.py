"""Semantic label APIs."""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import execute_query, execute_single, get_db, get_dbpath
from ..schema_runtime import qcolumn, qtable
from ..schema_keys import C, T

router = APIRouter(prefix="/semantic/labels")


@router.get("/by-character")
def get_semantic_label_by_character(
    char: str = Query(..., description="Character", min_length=1, max_length=1),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Get semantic label for one character."""
    try:
        table = qtable(dbpath, T.SEMANTIC_LABELS)
        char_col = qcolumn(dbpath, T.SEMANTIC_LABELS, C.SEMANTIC_LABELS.CHAR)
        category_col = qcolumn(dbpath, T.SEMANTIC_LABELS, C.SEMANTIC_LABELS.SEMANTIC_CATEGORY)
        confidence_col = qcolumn(dbpath, T.SEMANTIC_LABELS, C.SEMANTIC_LABELS.CONFIDENCE)
        explanation_col = qcolumn(dbpath, T.SEMANTIC_LABELS, C.SEMANTIC_LABELS.LLM_EXPLANATION)
        query = f"""
            SELECT
                {char_col} as character,
                {category_col} as semantic_category,
                {confidence_col} as confidence,
                {explanation_col} as llm_explanation
            FROM {table}
            WHERE {char_col} = ?
        """
        result = execute_single(db, query, (char,))
        if not result:
            raise HTTPException(status_code=404, detail=f"No semantic label found for character: {char}")
        return result
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            raise HTTPException(status_code=404, detail="Semantic labels data is not available")
        raise


@router.get("/by-category")
def get_characters_by_semantic_category(
    category: str = Query(..., description="Semantic category"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence"),
    limit: int = Query(100, ge=1, le=500, description="Max records"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Get characters in a semantic category."""
    try:
        table = qtable(dbpath, T.SEMANTIC_LABELS)
        char_col = qcolumn(dbpath, T.SEMANTIC_LABELS, C.SEMANTIC_LABELS.CHAR)
        category_col = qcolumn(dbpath, T.SEMANTIC_LABELS, C.SEMANTIC_LABELS.SEMANTIC_CATEGORY)
        confidence_col = qcolumn(dbpath, T.SEMANTIC_LABELS, C.SEMANTIC_LABELS.CONFIDENCE)
        explanation_col = qcolumn(dbpath, T.SEMANTIC_LABELS, C.SEMANTIC_LABELS.LLM_EXPLANATION)
        query = f"""
            SELECT
                {char_col} as character,
                {category_col} as semantic_category,
                {confidence_col} as confidence,
                {explanation_col} as llm_explanation
            FROM {table}
            WHERE {category_col} = ?
        """
        params = [category]

        if min_confidence is not None:
            query += f" AND {confidence_col} >= ?"
            params.append(min_confidence)

        query += f" ORDER BY {confidence_col} DESC LIMIT ?"
        params.append(limit)

        results = execute_query(db, query, tuple(params))
        if not results:
            raise HTTPException(status_code=404, detail=f"No characters found for category: {category}")

        return results
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            raise HTTPException(status_code=404, detail="Semantic labels data is not available")
        raise


@router.get("/categories")
def list_semantic_categories(
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """List semantic categories and their counts."""
    try:
        table = qtable(dbpath, T.SEMANTIC_LABELS)
        category_col = qcolumn(dbpath, T.SEMANTIC_LABELS, C.SEMANTIC_LABELS.SEMANTIC_CATEGORY)
        confidence_col = qcolumn(dbpath, T.SEMANTIC_LABELS, C.SEMANTIC_LABELS.CONFIDENCE)
        query = f"""
            SELECT
                {category_col} as semantic_category,
                COUNT(*) as character_count,
                AVG({confidence_col}) as avg_confidence
            FROM {table}
            GROUP BY {category_col}
            ORDER BY character_count DESC
        """
        results = execute_query(db, query)
        if not results:
            raise HTTPException(status_code=404, detail="No semantic categories found")

        return results
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            raise HTTPException(status_code=404, detail="Semantic labels data is not available")
        raise
