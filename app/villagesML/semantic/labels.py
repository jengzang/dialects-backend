"""Semantic label APIs."""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import execute_query, execute_single, get_db

router = APIRouter(prefix="/semantic/labels")


@router.get("/by-character")
def get_semantic_label_by_character(
    char: str = Query(..., description="Character", min_length=1, max_length=1),
    db: sqlite3.Connection = Depends(get_db),
):
    """Get semantic label for one character."""
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
):
    """Get characters in a semantic category."""
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

        if min_confidence is not None:
            query += " AND confidence >= ?"
            params.append(min_confidence)

        query += " ORDER BY confidence DESC LIMIT ?"
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
):
    """List semantic categories and their counts."""
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
            raise HTTPException(status_code=404, detail="No semantic categories found")

        return results
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            raise HTTPException(status_code=404, detail="Semantic labels data is not available")
        raise
