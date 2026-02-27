"""
语义子类别API
Semantic Subcategory API endpoints

Phase 17: 提供细化的语义子类别查询功能
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional, Dict
import sqlite3
import json
from pathlib import Path

from ..dependencies import get_db, execute_query

router = APIRouter(prefix="/semantic/subcategory", tags=["semantic"])

# 加载 v4_hybrid 词典
LEXICON_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "semantic_lexicon_v4_hybrid.json"


def load_lexicon() -> Dict:
    """加载 v4_hybrid 词典"""
    with open(LEXICON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


@router.get("/list")
def get_subcategories(
    parent_category: Optional[str] = Query(None, description="父类别过滤（mountain/water）")
):
    """
    获取所有子类别列表
    Get all subcategories

    Args:
        parent_category: 可选的父类别过滤

    Returns:
        Dict: 子类别列表及其字符
    """
    lexicon = load_lexicon()
    subcategories = lexicon.get("subcategories", {})

    if parent_category:
        # 过滤特定父类别的子类别
        filtered = {
            k: v for k, v in subcategories.items()
            if k.startswith(f"{parent_category}_")
        }
        if not filtered:
            raise HTTPException(
                status_code=404,
                detail=f"No subcategories found for parent category: {parent_category}"
            )
        return {
            "parent_category": parent_category,
            "subcategories": filtered,
            "count": len(filtered)
        }

    return {
        "subcategories": subcategories,
        "count": len(subcategories)
    }


@router.get("/chars/{subcategory}")
def get_subcategory_chars(subcategory: str):
    """
    获取特定子类别的字符列表
    Get characters for a specific subcategory

    Args:
        subcategory: 子类别名称（如 mountain_peak）

    Returns:
        Dict: 子类别信息及其字符列表
    """
    lexicon = load_lexicon()
    subcategories = lexicon.get("subcategories", {})

    if subcategory not in subcategories:
        raise HTTPException(
            status_code=404,
            detail=f"Subcategory not found: {subcategory}"
        )

    # 确定父类别
    parent = subcategory.split("_")[0] if "_" in subcategory else "unknown"

    return {
        "subcategory": subcategory,
        "parent_category": parent,
        "characters": subcategories[subcategory],
        "char_count": len(subcategories[subcategory])
    }


@router.get("/vtf/global")
def get_global_subcategory_vtf(
    parent_category: Optional[str] = Query(None, description="父类别过滤"),
    subcategory: Optional[str] = Query(None, description="子类别过滤"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数限制"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取全局子类别虚拟词频
    Get global subcategory virtual term frequency

    Args:
        parent_category: 可选的父类别过滤
        subcategory: 可选的子类别过滤
        limit: 返回记录数限制

    Returns:
        List[Dict]: 子类别 VTF 统计
    """
    query = """
        SELECT
            subcategory,
            parent_category,
            char_count,
            village_count,
            vtf,
            percentage
        FROM semantic_subcategory_vtf_global
        WHERE 1=1
    """
    params = []

    if parent_category:
        query += " AND parent_category = ?"
        params.append(parent_category)

    if subcategory:
        query += " AND subcategory = ?"
        params.append(subcategory)

    query += " ORDER BY vtf DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(status_code=404, detail="No subcategory VTF data found")

    return results


@router.get("/vtf/regional")
def get_regional_subcategory_vtf(
    region_level: str = Query("市级", description="区域级别（市级/区县级/乡镇级）"),
    region_name: Optional[str] = Query(None, description="区域名称"),
    parent_category: Optional[str] = Query(None, description="父类别过滤"),
    subcategory: Optional[str] = Query(None, description="子类别过滤"),
    min_tendency: Optional[float] = Query(None, description="最小倾向值"),
    min_villages: int = Query(0, ge=0, le=100, description="最小村庄数过滤（建议乡镇级使用5+）"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数限制"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取区域子类别虚拟词频
    Get regional subcategory virtual term frequency

    Args:
        region_level: 区域级别（市级/区县级/乡镇级）
        region_name: 可选的区域名称过滤
        parent_category: 可选的父类别过滤
        subcategory: 可选的子类别过滤
        min_tendency: 最小倾向值过滤
        min_villages: 最小村庄数过滤（建议乡镇级使用5+）
        limit: 返回记录数限制

    Returns:
        List[Dict]: 区域子类别 VTF 统计
    """
    query = """
        SELECT
            region_level,
            region_name,
            subcategory,
            parent_category,
            char_count,
            village_count,
            vtf,
            percentage,
            tendency
        FROM semantic_subcategory_vtf_regional
        WHERE region_level = ?
          AND village_count >= ?
    """
    params = [region_level, min_villages]

    if region_name:
        query += " AND region_name = ?"
        params.append(region_name)

    if parent_category:
        query += " AND parent_category = ?"
        params.append(parent_category)

    if subcategory:
        query += " AND subcategory = ?"
        params.append(subcategory)

    if min_tendency is not None:
        query += " AND tendency >= ?"
        params.append(min_tendency)

    query += " ORDER BY tendency DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(status_code=404, detail="No regional subcategory VTF data found")

    return results


@router.get("/tendency/top")
def get_top_tendency_subcategories(
    region_level: str = Query("市级", description="区域级别（市级/区县级/乡镇级）"),
    parent_category: Optional[str] = Query(None, description="父类别过滤"),
    min_villages: int = Query(5, ge=0, le=100, description="最小村庄数过滤（默认5，排除小样本噪声）"),
    top_n: int = Query(10, ge=1, le=50, description="返回前N个"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取倾向值最高的子类别
    Get subcategories with highest tendency values

    Args:
        region_level: 区域级别（市级/区县级/乡镇级）
        parent_category: 可选的父类别过滤
        min_villages: 最小村庄数过滤（默认5，排除小样本噪声）
        top_n: 返回前N个

    Returns:
        List[Dict]: 倾向值最高的子类别

    Note:
        - 默认过滤 village_count < 5 的数据，避免小样本噪声
        - 乡镇级数据建议使用更高的 min_villages 值（如10）
    """
    query = """
        SELECT
            region_name,
            subcategory,
            parent_category,
            tendency,
            percentage,
            village_count
        FROM semantic_subcategory_vtf_regional
        WHERE region_level = ?
          AND village_count >= ?
    """
    params = [region_level, min_villages]

    if parent_category:
        query += " AND parent_category = ?"
        params.append(parent_category)

    query += " ORDER BY tendency DESC LIMIT ?"
    params.append(top_n)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(status_code=404, detail="No tendency data found")

    return results


@router.get("/comparison")
def compare_subcategories(
    region_name: str = Query(..., description="区域名称"),
    region_level: str = Query("市级", description="区域级别（市级/区县级/乡镇级）"),
    parent_category: str = Query(..., description="父类别（mountain/water）"),
    min_villages: int = Query(0, ge=0, le=100, description="最小村庄数过滤（建议乡镇级使用5+）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    比较特定区域的子类别分布
    Compare subcategory distribution in a specific region

    Args:
        region_name: 区域名称
        region_level: 区域级别（市级/区县级/乡镇级）
        parent_category: 父类别（mountain/water等）
        min_villages: 最小村庄数过滤，用于排除小样本噪声（建议乡镇级使用5+）

    Returns:
        Dict: 子类别比较数据

    Note:
        - 乡镇级数据可能存在小样本噪声（村庄数<5），建议使用 min_villages=5 过滤
        - 数据覆盖：市级21个，区县级121个，乡镇级1439个
    """
    query = """
        SELECT
            subcategory,
            vtf,
            percentage,
            tendency,
            village_count
        FROM semantic_subcategory_vtf_regional
        WHERE region_level = ?
          AND region_name = ?
          AND parent_category = ?
          AND village_count >= ?
        ORDER BY vtf DESC
    """

    results = execute_query(db, query, (region_level, region_name, parent_category, min_villages))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {region_name} ({parent_category}) with min_villages >= {min_villages}"
        )

    return {
        "region_name": region_name,
        "region_level": region_level,
        "parent_category": parent_category,
        "min_villages": min_villages,
        "subcategories": results,
        "total_count": len(results)
    }
