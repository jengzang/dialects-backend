"""
语义组合分析API
Semantic Composition API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query, execute_single
from ..schema_runtime import normalize_region_level, qcolumn, qtable, table_variant
from ..schema_keys import C, TABLE_VARIANTS

router = APIRouter(prefix="/semantic")


@router.get("/composition/bigrams")
def get_semantic_bigrams(
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频率"),
    min_pmi: Optional[float] = Query(0.3, description="最小PMI值（默认0.3，过滤无意义组合）"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    detail: bool = Query(False, description="是否使用详细表（53子类别，v4词典）"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取语义二元组（bigram）
    Get semantic bigrams (two semantic categories co-occurring)

    Args:
        min_frequency: 最小频率（可选）
        min_pmi: 最小点互信息值（可选）
        limit: 返回记录数
        detail: 是否使用详细表（53子类别，v4词典），默认False（9大类别，v1词典）

    Returns:
        List[dict]: 语义二元组列表
    """
    logical_table = table_variant(dbpath, TABLE_VARIANTS.SEMANTIC_BIGRAMS_BY_DETAIL, detail)
    table = qtable(dbpath, logical_table)

    query = f"""
        SELECT
            {qcolumn(dbpath, logical_table, C.SEMANTIC_BIGRAMS.CATEGORY1)} as category1,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_BIGRAMS.CATEGORY2)} as category2,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_BIGRAMS.FREQUENCY)} as frequency,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_BIGRAMS.PERCENTAGE)} as percentage,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_BIGRAMS.PMI)} as pmi_score
        FROM {table}
        WHERE 1=1
    """
    params = []

    if min_frequency is not None:
        query += f" AND {qcolumn(dbpath, logical_table, C.SEMANTIC_BIGRAMS.FREQUENCY)} >= ?"
        params.append(min_frequency)

    if min_pmi is not None:
        query += f" AND {qcolumn(dbpath, logical_table, C.SEMANTIC_BIGRAMS.PMI)} >= ?"
        params.append(min_pmi)

    query += f" ORDER BY {qcolumn(dbpath, logical_table, C.SEMANTIC_BIGRAMS.FREQUENCY)} DESC LIMIT ?"
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
    detail: bool = Query(False, description="是否使用详细表（53子类别，v4词典）"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取语义三元组（trigram）
    Get semantic trigrams (three semantic categories co-occurring)

    Args:
        min_frequency: 最小频率（可选）
        limit: 返回记录数
        detail: 是否使用详细表（53子类别，v4词典），默认False（9大类别，v1词典）

    Returns:
        List[dict]: 语义三元组列表
    """
    logical_table = table_variant(dbpath, TABLE_VARIANTS.SEMANTIC_TRIGRAMS_BY_DETAIL, detail)
    table = qtable(dbpath, logical_table)

    query = f"""
        SELECT
            {qcolumn(dbpath, logical_table, C.SEMANTIC_TRIGRAMS.CATEGORY1)} as category1,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_TRIGRAMS.CATEGORY2)} as category2,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_TRIGRAMS.CATEGORY3)} as category3,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_TRIGRAMS.FREQUENCY)} as frequency,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_TRIGRAMS.PERCENTAGE)} as percentage
        FROM {table}
        WHERE 1=1
    """
    params = []

    if min_frequency is not None:
        query += f" AND {qcolumn(dbpath, logical_table, C.SEMANTIC_TRIGRAMS.FREQUENCY)} >= ?"
        params.append(min_frequency)

    query += f" ORDER BY {qcolumn(dbpath, logical_table, C.SEMANTIC_TRIGRAMS.FREQUENCY)} DESC LIMIT ?"
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
    detail: bool = Query(False, description="是否使用详细表（53子类别，v4词典）"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取语义点互信息（PMI）
    Get semantic pointwise mutual information scores

    Args:
        category1: 第一个语义类别（可选）
        category2: 第二个语义类别（可选）
        min_pmi: 最小PMI值（可选）
        limit: 返回记录数
        detail: 是否使用详细表（53子类别，v4词典），默认False（9大类别，v1词典）

    Returns:
        List[dict]: PMI分数列表
    """
    logical_table = table_variant(dbpath, TABLE_VARIANTS.SEMANTIC_PMI_BY_DETAIL, detail)
    table = qtable(dbpath, logical_table)

    query = f"""
        SELECT
            {qcolumn(dbpath, logical_table, C.SEMANTIC_PMI.CATEGORY1)} as category1,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_PMI.CATEGORY2)} as category2,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_PMI.PMI)} as pmi_score,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_PMI.FREQUENCY)} as frequency,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_PMI.IS_POSITIVE)} as is_positive
        FROM {table}
        WHERE 1=1
    """
    params = []

    if category1 is not None:
        query += f" AND {qcolumn(dbpath, logical_table, C.SEMANTIC_PMI.CATEGORY1)} = ?"
        params.append(category1)

    if category2 is not None:
        query += f" AND {qcolumn(dbpath, logical_table, C.SEMANTIC_PMI.CATEGORY2)} = ?"
        params.append(category2)

    if min_pmi is not None:
        query += f" AND {qcolumn(dbpath, logical_table, C.SEMANTIC_PMI.PMI)} >= ?"
        params.append(min_pmi)

    query += f" ORDER BY {qcolumn(dbpath, logical_table, C.SEMANTIC_PMI.PMI)} DESC LIMIT ?"
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
    detail: bool = Query(False, description="是否使用详细表（53子类别，v4词典）"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取语义组合模式
    Get semantic composition patterns

    Args:
        pattern_type: 模式类型（可选）
        min_frequency: 最小频率（可选）
        limit: 返回记录数
        detail: 是否使用详细表（53子类别，v4词典），默认False（9大类别，v1词典）

    Returns:
        List[dict]: 组合模式列表
    """
    logical_table = table_variant(dbpath, TABLE_VARIANTS.SEMANTIC_COMPOSITION_PATTERNS_BY_DETAIL, detail)
    table = qtable(dbpath, logical_table)

    query = f"""
        SELECT
            {qcolumn(dbpath, logical_table, C.SEMANTIC_COMPOSITION_PATTERNS.PATTERN)} as pattern,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_COMPOSITION_PATTERNS.PATTERN_TYPE)} as pattern_type,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_COMPOSITION_PATTERNS.MODIFIER)} as modifier,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_COMPOSITION_PATTERNS.HEAD)} as head,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_COMPOSITION_PATTERNS.FREQUENCY)} as frequency,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_COMPOSITION_PATTERNS.PERCENTAGE)} as percentage,
            {qcolumn(dbpath, logical_table, C.SEMANTIC_COMPOSITION_PATTERNS.DESCRIPTION)} as description
        FROM {table}
        WHERE 1=1
    """
    params = []

    if pattern_type is not None:
        query += f" AND {qcolumn(dbpath, logical_table, C.SEMANTIC_COMPOSITION_PATTERNS.PATTERN_TYPE)} = ?"
        params.append(pattern_type)

    if min_frequency is not None:
        query += f" AND {qcolumn(dbpath, logical_table, C.SEMANTIC_COMPOSITION_PATTERNS.FREQUENCY)} >= ?"
        params.append(min_frequency)

    query += f" ORDER BY {qcolumn(dbpath, logical_table, C.SEMANTIC_COMPOSITION_PATTERNS.FREQUENCY)} DESC LIMIT ?"
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
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    min_villages: Optional[int] = Query(None, ge=1, description="最小村庄数（过滤小样本区域）"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    detail: bool = Query(False, description="是否使用详细表（53子类别，v4词典）"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath)
):
    """
    获取语义强度指数
    Get semantic intensity indices

    Args:
        category: 语义类别（可选）
        region_level: 区域级别（可选）
        region_name: 区域名称（模糊匹配，向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        min_villages: 最小村庄数，过滤村庄数少的区域（可选）
        limit: 返回记录数
        detail: 是否使用详细表（53子类别，v4词典），默认False（9大类别，v1词典）

    Returns:
        List[dict]: 语义指数列表
    """
    logical_table = table_variant(dbpath, TABLE_VARIANTS.SEMANTIC_INDICES_BY_DETAIL, detail)
    table = qtable(dbpath, logical_table)
    region_level_col = qcolumn(dbpath, logical_table, C.SEMANTIC_INDICES.REGION_LEVEL)
    region_name_col = qcolumn(dbpath, logical_table, C.SEMANTIC_INDICES.REGION_NAME)
    city_col = qcolumn(dbpath, logical_table, C.SEMANTIC_INDICES.CITY)
    county_col = qcolumn(dbpath, logical_table, C.SEMANTIC_INDICES.COUNTY)
    township_col = qcolumn(dbpath, logical_table, C.SEMANTIC_INDICES.TOWNSHIP)
    category_col = qcolumn(dbpath, logical_table, C.SEMANTIC_INDICES.CATEGORY)
    raw_intensity_col = qcolumn(dbpath, logical_table, C.SEMANTIC_INDICES.RAW_INTENSITY)
    normalized_index_col = qcolumn(dbpath, logical_table, C.SEMANTIC_INDICES.NORMALIZED_INDEX)
    rank_col = qcolumn(dbpath, logical_table, C.SEMANTIC_INDICES.RANK_WITHIN_PROVINCE)
    village_count_col = qcolumn(dbpath, logical_table, C.SEMANTIC_INDICES.VILLAGE_COUNT)

    # Use pre-computed village_count column for optimal performance
    query = f"""
        SELECT
            {region_level_col} as region_level,
            {region_name_col} as region_name,
            {city_col} as city,
            {county_col} as county,
            {township_col} as township,
            {category_col} as semantic_category,
            {raw_intensity_col} as semantic_index,
            {normalized_index_col} as normalized_index,
            {rank_col} as rank_in_region,
            {village_count_col} as village_count
        FROM {table}
        WHERE 1=1
    """
    params = []

    if category is not None:
        if detail:
            query += f" AND ({category_col} = ? OR {category_col} LIKE '%$_' || ? ESCAPE '$')"
            params.append(category)
            params.append(category)
        else:
            query += f" AND {category_col} = ?"
            params.append(category)

    if region_level is not None:
        query += f" AND {region_level_col} = ?"
        params.append(normalize_region_level(dbpath, logical_table, region_level))

    # Priority 1: Use hierarchy parameters (exact match)
    if city is not None:
        query += f" AND {city_col} = ?"
        params.append(city)
    if county is not None:
        query += f" AND {county_col} = ?"
        params.append(county)
    elif city is not None and region_level == 'township':
        # Handle 东莞市/中山市 (no county level)
        query += f" AND ({county_col} IS NULL OR {county_col} = '')"
    if township is not None:
        query += f" AND {township_col} = ?"
        params.append(township)

    # Priority 2: Backward compatibility (fuzzy match)
    if region_name is not None:
        query += f" AND ({city_col} = ? OR {county_col} = ? OR {township_col} = ?)"
        params.extend([region_name, region_name, region_name])

    if min_villages is not None:
        query += f" AND {village_count_col} >= ?"
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
