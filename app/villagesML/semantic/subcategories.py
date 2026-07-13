"""Semantic subcategory API endpoints."""

from pathlib import Path
import json
import sqlite3
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import execute_query, get_db, get_dbpath
from ..schema_runtime import qcolumn, qtable

router = APIRouter(prefix="/semantic/subcategory")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LEXICON_PATH = PROJECT_ROOT / "data" / "semantic_lexicon_v4.json"
LEGACY_LEXICON_PATH = PROJECT_ROOT.parent / "data" / "semantic_lexicon_v4.json"


def _subcategory_schema(dbpath: str, logical_table: str):
    return qtable(dbpath, logical_table), lambda name: qcolumn(dbpath, logical_table, name)


def load_lexicon() -> Dict:
    """Load the semantic lexicon from disk."""
    lexicon_path = LEXICON_PATH if LEXICON_PATH.exists() else LEGACY_LEXICON_PATH
    if not lexicon_path.exists():
        raise HTTPException(status_code=404, detail="Semantic lexicon is not available on server")

    try:
        with open(lexicon_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Semantic lexicon file is corrupted")

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Semantic lexicon format is invalid")

    return data


@router.get("/list")
def get_subcategories(
    parent_category: Optional[str] = Query(None, description="Parent category filter (mountain/water)"),
):
    """Get all subcategories, optionally filtered by parent category."""
    lexicon = load_lexicon()
    subcategories = lexicon.get("subcategories", {})

    if parent_category:
        filtered = {
            key: value
            for key, value in subcategories.items()
            if key.startswith(f"{parent_category}_")
        }
        if not filtered:
            raise HTTPException(
                status_code=404,
                detail=f"No subcategories found for parent category: {parent_category}",
            )
        return {
            "parent_category": parent_category,
            "subcategories": filtered,
            "count": len(filtered),
        }

    return {
        "subcategories": subcategories,
        "count": len(subcategories),
    }


@router.get("/chars/{subcategory}")
def get_subcategory_chars(subcategory: str):
    """Get characters under a specific semantic subcategory."""
    lexicon = load_lexicon()
    subcategories = lexicon.get("subcategories", {})

    if subcategory not in subcategories:
        raise HTTPException(status_code=404, detail=f"Subcategory not found: {subcategory}")

    parent = subcategory.split("_")[0] if "_" in subcategory else "unknown"

    return {
        "subcategory": subcategory,
        "parent_category": parent,
        "characters": subcategories[subcategory],
        "char_count": len(subcategories[subcategory]),
    }


@router.get("/vtf/global")
def get_global_subcategory_vtf(
    parent_category: Optional[str] = Query(None, description="Parent category filter"),
    subcategory: Optional[str] = Query(None, description="Subcategory filter"),
    limit: int = Query(100, ge=1, le=1000, description="Max records"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Get global subcategory VTF metrics."""
    table, col = _subcategory_schema(dbpath, "semantic_subcategory_vtf_global")
    query = f"""
        SELECT
            {col("subcategory")} as subcategory,
            {col("parent_category")} as parent_category,
            {col("char_count")} as char_count,
            {col("village_count")} as village_count,
            {col("vtf")} as vtf,
            {col("percentage")} as percentage
        FROM {table}
        WHERE 1=1
    """
    params: List[object] = []

    if parent_category:
        query += f" AND {col('parent_category')} = ?"
        params.append(parent_category)

    if subcategory:
        query += f" AND {col('subcategory')} = ?"
        params.append(subcategory)

    query += f" ORDER BY {col('vtf')} DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))
    if not results:
        raise HTTPException(status_code=404, detail="No subcategory VTF data found")

    return results


@router.get("/vtf/regional")
def get_regional_subcategory_vtf(
    region_level: str = Query("市级", description="Region level (市级/区县级/乡镇级)"),
    region_name: Optional[str] = Query(None, description="Region name"),
    parent_category: Optional[str] = Query(None, description="Parent category filter"),
    subcategory: Optional[str] = Query(None, description="Subcategory filter"),
    min_tendency: Optional[float] = Query(None, description="Minimum tendency"),
    min_villages: int = Query(0, ge=0, le=100, description="Minimum village count"),
    limit: int = Query(100, ge=1, le=1000, description="Max records"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Get regional subcategory VTF metrics."""
    table, col = _subcategory_schema(dbpath, "semantic_subcategory_vtf_regional")
    query = f"""
        SELECT
            {col("region_level")} as region_level,
            {col("region_name")} as region_name,
            {col("subcategory")} as subcategory,
            {col("parent_category")} as parent_category,
            {col("char_count")} as char_count,
            {col("village_count")} as village_count,
            {col("vtf")} as vtf,
            {col("percentage")} as percentage,
            {col("tendency")} as tendency
        FROM {table}
        WHERE {col("region_level")} = ?
          AND {col("village_count")} >= ?
    """
    params: List[object] = [region_level, min_villages]

    if region_name:
        query += f" AND {col('region_name')} = ?"
        params.append(region_name)

    if parent_category:
        query += f" AND {col('parent_category')} = ?"
        params.append(parent_category)

    if subcategory:
        query += f" AND {col('subcategory')} = ?"
        params.append(subcategory)

    if min_tendency is not None:
        query += f" AND {col('tendency')} >= ?"
        params.append(min_tendency)

    query += f" ORDER BY {col('tendency')} DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))
    if not results:
        raise HTTPException(status_code=404, detail="No regional subcategory VTF data found")

    return results


@router.get("/tendency/top")
def get_top_tendency_subcategories(
    region_level: str = Query("市级", description="Region level (市级/区县级/乡镇级)"),
    parent_category: Optional[str] = Query(None, description="Parent category filter"),
    min_villages: int = Query(5, ge=0, le=100, description="Minimum village count"),
    top_n: int = Query(10, ge=1, le=100, description="Top N records"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Get top-N subcategories by tendency."""
    table, col = _subcategory_schema(dbpath, "semantic_subcategory_vtf_regional")
    query = f"""
        SELECT
            {col("region_name")} as region_name,
            {col("subcategory")} as subcategory,
            {col("parent_category")} as parent_category,
            {col("tendency")} as tendency,
            {col("percentage")} as percentage,
            {col("village_count")} as village_count
        FROM {table}
        WHERE {col("region_level")} = ?
          AND {col("village_count")} >= ?
    """
    params: List[object] = [region_level, min_villages]

    if parent_category:
        query += f" AND {col('parent_category')} = ?"
        params.append(parent_category)

    query += f" ORDER BY {col('tendency')} DESC LIMIT ?"
    params.append(top_n)

    results = execute_query(db, query, tuple(params))
    if not results:
        raise HTTPException(status_code=404, detail="No tendency data found")

    return results


@router.get("/comparison")
def compare_subcategories(
    region_name: str = Query(..., description="Region name"),
    region_level: str = Query("市级", description="Region level (市级/区县级/乡镇级)"),
    parent_category: str = Query(..., description="Parent category"),
    min_villages: int = Query(0, ge=0, le=100, description="Minimum village count"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """Compare subcategory distribution for a specific region and parent category."""
    table, col = _subcategory_schema(dbpath, "semantic_subcategory_vtf_regional")
    query = f"""
        SELECT
            {col("subcategory")} as subcategory,
            {col("vtf")} as vtf,
            {col("percentage")} as percentage,
            {col("tendency")} as tendency,
            {col("village_count")} as village_count
        FROM {table}
        WHERE {col("region_level")} = ?
          AND {col("region_name")} = ?
          AND {col("parent_category")} = ?
          AND {col("village_count")} >= ?
        ORDER BY {col("vtf")} DESC
    """

    results = execute_query(db, query, (region_level, region_name, parent_category, min_villages))
    if not results:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No data found for {region_name} ({parent_category}) "
                f"with min_villages >= {min_villages}"
            ),
        )

    return {
        "region_name": region_name,
        "region_level": region_level,
        "parent_category": parent_category,
        "min_villages": min_villages,
        "subcategories": results,
        "total_count": len(results),
    }
