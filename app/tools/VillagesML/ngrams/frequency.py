"""
N-gram分析API
N-gram Analysis API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional, Dict, Any
import sqlite3
from datetime import datetime

from ..dependencies import get_db, execute_query
from ..config import DEFAULT_RUN_ID
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/ngrams")

# 数据优化配置
DATA_OPTIMIZATION_DATE = None  # 将在数据优化后设置，格式: "2026-02-25"
DATA_RETENTION_RATE = 1.0  # 数据保留率，优化后会更新为 0.587
INCLUDES_INSIGNIFICANT = True  # 是否包含不显著数据，优化后会设置为 False


def _build_metadata(
    total_count: int,
    includes_insignificant: bool = INCLUDES_INSIGNIFICANT
) -> Dict[str, Any]:
    """
    构建响应元数据

    Args:
        total_count: 返回的记录数
        includes_insignificant: 是否包含不显著数据

    Returns:
        元数据字典
    """
    metadata = {
        "total_count": total_count,
        "includes_insignificant": includes_insignificant
    }

    if DATA_OPTIMIZATION_DATE:
        metadata["note"] = "Only statistically significant n-grams (p < 0.05) are included"
        metadata["data_version"] = f"optimized_{DATA_OPTIMIZATION_DATE.replace('-', '')}"
        metadata["optimization_date"] = DATA_OPTIMIZATION_DATE
        metadata["coverage_rate"] = DATA_RETENTION_RATE

    return metadata


@router.get("/frequency")
def get_ngram_frequency(
    n: int = Query(..., ge=2, le=4, description="N-gram大小 (2=bigram, 3=trigram)"),
    position: str = Query("all", pattern="^(all|prefix|middle|suffix)$", description="N-gram位置 (all=所有位置, prefix=前缀, middle=中间, suffix=后缀)"),
    top_k: int = Query(100, ge=1, le=1000, description="返回前K个n-grams"),
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频次过滤"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取全局N-gram频率
    Get global n-gram frequencies

    Args:
        n: N-gram大小 (2, 3, 或 4)
        position: N-gram位置 (all=所有位置, prefix=前缀, middle=中间, suffix=后缀)
        top_k: 返回前K个高频n-grams
        min_frequency: 最小频次阈值（可选）

    Returns:
        List[dict]: N-gram频率列表
    """
    query = """
        SELECT
            ngram,
            position,
            frequency,
            percentage
        FROM ngram_frequency
        WHERE n = ? AND position = ?
    """
    params = [n, position]

    # 现场过滤：最小频次
    if min_frequency is not None:
        query += " AND frequency >= ?"
        params.append(min_frequency)

    query += " ORDER BY frequency DESC LIMIT ?"
    params.append(top_k)

    # Debug: print the query
    # print(f"DEBUG: Query = {query}")
    # print(f"DEBUG: Params = {params}")

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No {n}-grams found"
        )

    return results


@router.get("/regional")
def get_regional_ngram_frequency(
    n: int = Query(..., ge=2, le=4, description="N-gram大小"),
    region_level: str = Query("township", description="区域级别（当前仅支持 township）", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    top_k: int = Query(50, ge=1, le=500, description="每个区域返回前K个n-grams"),
    return_metadata: bool = Query(False, description="是否返回元数据（包含数据说明）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取区域N-gram频率
    Get regional n-gram frequencies

    注意：
    - 当前数据仅包含 township (乡镇) 级别
    - 查询 city 或 county 级别会返回 404
    - 表中没有 run_id 字段，数据是静态的

    Args:
        n: N-gram大小
        region_level: 区域级别 (city/county/township)，当前仅 township 有数据
        region_name: 区域名称（模糊匹配，可选，向后兼容）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        top_k: 每个区域返回前K个n-grams
        return_metadata: 是否返回元数据

    Returns:
        List[dict] 或 dict: N-gram频率列表，或包含data和metadata的字典
    """
    # 注意：表结构中字段名是 level，不是 region_level
    # 使用子查询添加 rank
    query = """
        SELECT
            level as region_level,
            region as region_name,
            city,
            county,
            township,
            ngram,
            frequency,
            percentage,
            ROW_NUMBER() OVER (PARTITION BY region ORDER BY frequency DESC) as rank
        FROM regional_ngram_frequency
        WHERE n = ? AND level = ?
    """
    params = [n, region_level]

    # 优先使用层级参数（精确匹配）
    if city is not None:
        query += " AND city = ?"
        params.append(city)
    if county is not None:
        query += " AND county = ?"
        params.append(county)
    if township is not None:
        query += " AND township = ?"
        params.append(township)

    # 向后兼容：region_name（模糊匹配）
    if region_name is not None:
        query += " AND region = ?"
        params.append(region_name)

    # 包装为子查询以应用 rank 过滤
    query = f"""
        SELECT * FROM (
            {query}
        ) WHERE rank <= ?
        ORDER BY region_name, rank
    """
    params.append(top_k)

    results = execute_query(db, query, tuple(params))

    if not results:
        # 提供更友好的错误信息
        if region_level in ['city', 'county']:
            detail = f"No data available for region_level='{region_level}'. Currently only 'township' level data is available in the database."
        else:
            detail = f"No regional {n}-grams found with the given filters."

        raise HTTPException(
            status_code=404,
            detail=detail
        )

    # 如果需要返回元数据
    if return_metadata:
        return {
            "data": results,
            "metadata": _build_metadata(len(results))
        }

    return results


@router.get("/patterns")
def get_structural_patterns(
    pattern: Optional[str] = Query(None, description="模式过滤（*或X表示占位符，如'山*'或'山X'；支持SQL LIKE语法，如'山%'表示以山开头）"),
    pattern_type: Optional[str] = Query(None, description="模式类型过滤"),
    n: Optional[int] = Query(None, ge=2, le=4, description="N-gram大小过滤"),
    position: Optional[str] = Query(None, pattern="^(all|prefix|middle|suffix)$", description="位置过滤"),
    min_frequency: Optional[int] = Query(None, ge=1, description="最小频次过滤"),
    limit: int = Query(100, ge=1, le=500, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取结构化命名模式
    Get structural naming patterns

    Args:
        pattern: 模式过滤（*或X表示占位符；支持SQL LIKE语法）
        pattern_type: 模式类型（可选）
        n: N-gram大小（可选）
        position: 位置过滤（可选）
        min_frequency: 最小频次（可选）
        limit: 返回记录数

    Returns:
        List[dict]: 结构化模式列表
    """
    query = """
        SELECT
            pattern,
            pattern_type,
            n,
            position,
            frequency,
            example
        FROM structural_patterns
    """
    params = []

    # 现场过滤
    conditions = []

    # 模式过滤（支持 LIKE，同时支持 * 和 X 作为占位符）
    if pattern is not None:
        # 将 * 替换为 X（数据库中使用 X 作为占位符）
        normalized_pattern = pattern.replace('*', 'X')

        # 智能模糊匹配：如果不包含通配符（%、_、X），自动添加 % 进行模糊匹配
        if '%' not in normalized_pattern and '_' not in normalized_pattern and 'X' not in normalized_pattern:
            normalized_pattern = f'%{normalized_pattern}%'

        conditions.append("pattern LIKE ?")
        params.append(normalized_pattern)

    # 模式类型过滤
    if pattern_type is not None:
        conditions.append("pattern_type = ?")
        params.append(pattern_type)

    # N-gram 大小过滤
    if n is not None:
        conditions.append("n = ?")
        params.append(n)

    # 位置过滤
    if position is not None:
        conditions.append("position = ?")
        params.append(position)

    # 最小频次过滤
    if min_frequency is not None:
        conditions.append("frequency >= ?")
        params.append(min_frequency)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY frequency DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        # 提供更详细的错误信息
        error_msg = "No structural patterns found"
        if n is not None:
            error_msg += f" for n={n}"
        if pattern is not None:
            error_msg += f" matching pattern '{pattern}'"
        error_msg += ". Note: Currently only n=2 (bigram) patterns are available in the database."

        raise HTTPException(
            status_code=404,
            detail=error_msg
        )

    return results


@router.get("/tendency")
def get_ngram_tendency(
    ngram: Optional[str] = Query(None, description="N-gram（2-4字符，如'新村'、'村村'）"),
    region_level: str = Query("township", description="区域级别（当前数据仅包含township）", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="区县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    min_tendency: Optional[float] = Query(None, description="最小倾向值（lift值）"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取N-gram倾向性分析
    Get n-gram tendency scores

    注意：
    - 当前数据仅包含 township (乡镇) 级别的倾向性
    - 如果查询 city 或 county 级别会返回 404
    - ngram 必须是 2-4 字符的组合（如"新村"、"山村"），不支持单字符
    - 倾向值 (lift) > 1 表示该区域偏好使用该 n-gram
    - 倾向值 (lift) < 1 表示该区域较少使用该 n-gram

    Args:
        ngram: N-gram内容（2-4字符）
        region_level: 区域级别（city/county/township，当前仅 township 有数据）
        region_name: 区域名称（模糊匹配）
        city: 市级过滤（精确匹配）
        county: 区县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        min_tendency: 最小倾向值（lift值）
        limit: 返回记录数

    Returns:
        List[dict]: N-gram倾向性列表（包含区域中心点坐标）
    """
    # 根据 region_level 确定坐标计算的字段
    if region_level == 'city':
        coord_field = '市级'
    elif region_level == 'county':
        coord_field = '区县级'
    else:  # township
        coord_field = '乡镇级'

    query = f"""
        SELECT
            nt.level as region_level,
            nt.region as region_name,
            nt.city,
            nt.county,
            nt.township,
            nt.ngram,
            nt.n,
            nt.position,
            nt.lift as tendency_score,
            nt.log_odds,
            nt.z_score,
            nt.regional_count as frequency,
            nt.regional_total,
            nt.global_count as expected_frequency,
            nt.global_total,
            AVG(v.longitude) as centroid_lon,
            AVG(v.latitude) as centroid_lat
        FROM ngram_tendency nt
        LEFT JOIN 广东省自然村_预处理 v ON nt.region = v.{coord_field}
        WHERE nt.level = ?
    """
    params = [region_level]

    # 优先使用层级参数（精确匹配）
    if city is not None:
        query += " AND nt.city = ?"
        params.append(city)
    if county is not None:
        query += " AND nt.county = ?"
        params.append(county)
    if township is not None:
        query += " AND nt.township = ?"
        params.append(township)

    # 向后兼容：region_name（模糊匹配）
    if region_name is not None:
        query += " AND nt.region = ?"
        params.append(region_name)

    if ngram is not None:
        query += " AND nt.ngram = ?"
        params.append(ngram)

    if min_tendency is not None:
        query += " AND nt.lift >= ?"
        params.append(min_tendency)

    query += """
        GROUP BY nt.level, nt.region, nt.city, nt.county, nt.township,
                 nt.ngram, nt.n, nt.position, nt.lift, nt.log_odds, nt.z_score,
                 nt.regional_count, nt.regional_total, nt.global_count, nt.global_total
        ORDER BY nt.lift DESC
        LIMIT ?
    """
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        # 提供更友好的错误信息
        if region_level in ['city', 'county']:
            detail = f"No data available for region_level='{region_level}'. Currently only 'township' level data is available."
        elif ngram and len(ngram) == 1:
            detail = f"No data found for single character '{ngram}'. Only n-grams (2-4 chars) are supported. Try using character tendency endpoints instead."
        else:
            detail = "No n-gram tendency data found with the given filters."

        raise HTTPException(status_code=404, detail=detail)

    return results


@router.get("/significance")


@router.get("/significance")
def get_ngram_significance(
    ngram: Optional[str] = Query(None, description="N-gram"),
    region_level: str = Query("county", description="区域级别"),
    is_significant: Optional[bool] = Query(None, description="仅显示显著结果"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取N-gram显著性
    Get n-gram significance test results

    注意：表中字段名是 level，不是 region_level
    """
    query = """
        SELECT
            level as region_level,
            region as region_name,
            city,
            county,
            township,
            ngram,
            n,
            position,
            chi2 as z_score,
            p_value,
            is_significant,
            cramers_v as lift
        FROM ngram_significance
        WHERE level = ?
    """
    params = [region_level]

    if ngram is not None:
        query += " AND ngram = ?"
        params.append(ngram)

    if is_significant is not None:
        query += " AND is_significant = ?"
        params.append(1 if is_significant else 0)

    query += " ORDER BY ABS(chi2) DESC LIMIT ?"
    params.append(limit)

    results = execute_query(db, query, tuple(params))

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No n-gram significance data found"
        )

    return results
