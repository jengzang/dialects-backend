"""
语义组合分析API
Semantic Composition API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single

router = APIRouter(prefix="/semantic", tags=["semantic-composition"])


@router.get("/composition/bigrams")
def get_semantic_bigrams(
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频率"),
    min_pmi: Optional[float] = Query(0.3, description="最小PMI值（默认0.3，过滤无意义组合）"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取语义二元组（bigram）
    Get semantic bigrams (two semantic categories co-occurring)

    Args:
        min_frequency: 最小频率（可选）
        min_pmi: 最小点互信息值（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 语义二元组列表
    """
    query = """
        SELECT
            category1,
            category2,
            frequency,
            percentage,
            pmi as pmi_score
        FROM semantic_bigrams
        WHERE 1=1
    """
    params = []

    if min_frequency is not None:
        query += " AND frequency >= ?"
        params.append(min_frequency)

    if min_pmi is not None:
        query += " AND pmi >= ?"
        params.append(min_pmi)

    query += " ORDER BY frequency DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No semantic bigrams found"
        )

    return results


@router.get("/composition/trigrams")
def get_semantic_trigrams(
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频率"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取语义三元组（trigram）
    Get semantic trigrams (three semantic categories co-occurring)

    Args:
        min_frequency: 最小频率（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 语义三元组列表
    """
    query = """
        SELECT
            category1,
            category2,
            category3,
            frequency,
            percentage
        FROM semantic_trigrams
        WHERE 1=1
    """
    params = []

    if min_frequency is not None:
        query += " AND frequency >= ?"
        params.append(min_frequency)

    query += " ORDER BY frequency DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No semantic trigrams found"
        )

    return results


@router.get("/composition/pmi")
def get_semantic_pmi(
    category1: Optional[str] = Query(None, description="第一个语义类别"),
    category2: Optional[str] = Query(None, description="第二个语义类别"),
    min_pmi: Optional[float] = Query(None, description="最小PMI值"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取语义点互信息（PMI）
    Get semantic pointwise mutual information scores

    Args:
        category1: 第一个语义类别（可选）
        category2: 第二个语义类别（可选）
        min_pmi: 最小PMI值（可选）
        limit: 返回记录数

    Returns:
        List[dict]: PMI分数列表
    """
    query = """
        SELECT
            category1,
            category2,
            pmi as pmi_score,
            frequency,
            is_positive
        FROM semantic_pmi
        WHERE 1=1
    """
    params = []

    if category1 is not None:
        query += " AND category1 = ?"
        params.append(category1)

    if category2 is not None:
        query += " AND category2 = ?"
        params.append(category2)

    if min_pmi is not None:
        query += " AND pmi >= ?"
        params.append(min_pmi)

    query += " ORDER BY pmi DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No PMI scores found"
        )

    return results


@router.get("/composition/patterns")
def get_composition_patterns(
    pattern_type: Optional[str] = Query(None, description="模式类型"),
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频率"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取语义组合模式
    Get semantic composition patterns

    Args:
        pattern_type: 模式类型（可选）
        min_frequency: 最小频率（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 组合模式列表
    """
    query = """
        SELECT
            pattern,
            pattern_type,
            modifier,
            head,
            frequency,
            percentage,
            description
        FROM semantic_composition_patterns
        WHERE 1=1
    """
    params = []

    if pattern_type is not None:
        query += " AND pattern_type = ?"
        params.append(pattern_type)

    if min_frequency is not None:
        query += " AND frequency >= ?"
        params.append(min_frequency)

    query += " ORDER BY frequency DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No composition patterns found"
        )

    return results


@router.get("/indices")
def get_semantic_indices(
    category: Optional[str] = Query(None, description="语义类别"),
    region_level: Optional[str] = Query(None, description="区域级别"),
    region_name: Optional[str] = Query(None, description="区域名称"),
    min_villages: Optional[int] = Query(None, ge=1, description="最小村庄数（过滤小样本区域）"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取语义强度指数
    Get semantic intensity indices

    Args:
        category: 语义类别（可选）
        region_level: 区域级别（可选）
        region_name: 区域名称（可选）
        min_villages: 最小村庄数，过滤村庄数少的区域（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 语义指数列表
    """
    # If min_villages is specified, need to JOIN with main table to count villages
    if min_villages is not None:
        query = """
            SELECT
                si.region_level,
                si.region_name,
                si.category as semantic_category,
                si.raw_intensity as semantic_index,
                si.normalized_index,
                si.rank_within_province as rank_in_region,
                COUNT(DISTINCT v.自然村) as village_count
            FROM semantic_indices si
            LEFT JOIN 广东省自然村 v ON (
                (si.region_level = 'city' AND si.region_name = v.市级) OR
                (si.region_level = 'county' AND si.region_name = v.区县级) OR
                (si.region_level = 'township' AND si.region_name = v.乡镇级)
            )
            WHERE 1=1
        """
    else:
        query = """
            SELECT
                region_level,
                region_name,
                category as semantic_category,
                raw_intensity as semantic_index,
                normalized_index,
                rank_within_province as rank_in_region
            FROM semantic_indices
            WHERE 1=1
        """

    params = []

    if category is not None:
        if min_villages is not None:
            query += " AND si.category = ?"
        else:
            query += " AND semantic_category = ?"
        params.append(category)

    if region_level is not None:
        if min_villages is not None:
            query += " AND si.region_level = ?"
        else:
            query += " AND region_level = ?"
        params.append(region_level)

    if region_name is not None:
        if min_villages is not None:
            query += " AND si.region_name = ?"
        else:
            query += " AND region_name = ?"
        params.append(region_name)

    # Add GROUP BY and HAVING for min_villages filter
    if min_villages is not None:
        query += """
            GROUP BY si.region_level, si.region_name, si.category,
                     si.raw_intensity, si.normalized_index, si.rank_within_province
            HAVING village_count >= ?
        """
        params.append(min_villages)

    query += " ORDER BY semantic_index DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No semantic indices found"
        )

    return results
