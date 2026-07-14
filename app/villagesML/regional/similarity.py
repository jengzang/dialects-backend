"""
Region Similarity API Endpoints

Provides endpoints for querying region similarity metrics.
Phase 15: 区域相似度分析
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
import sqlite3
import json

from ..dependencies import get_db, get_dbpath, execute_query, execute_single
from ..schema_runtime import column_name, qcolumn, qtable, normalize_region_level
from ..schema_keys import C, SIMILARITY_METRIC_COLUMNS, T

router = APIRouter(prefix="/regions")


def _regional_schema(dbpath: str, logical_table: str):
    return qtable(dbpath, logical_table), lambda name: qcolumn(dbpath, logical_table, name)


@router.get("/similarity/search")
async def search_similar_regions(
    region_level: str = Query(..., description="区域级别", pattern="^(city|county|township)$"),
    region_name: Optional[str] = Query(None, description="区域名称（模糊匹配，向后兼容）"),
    city: Optional[str] = Query(None, description="市级过滤"),
    county: Optional[str] = Query(None, description="县级过滤"),
    township: Optional[str] = Query(None, description="乡镇级过滤"),
    top_k: int = Query(10, ge=1, le=50, description="返回相似区域数量"),
    metric: str = Query("cosine", regex="^(cosine|jaccard)$", description="相似度指标"),
    min_similarity: float = Query(0.0, ge=0.0, le=1.0, description="最小相似度阈值"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    查找与目标区域相似的其他区域

    Find regions similar to a target region.

    Args:
        region_level: 区域级别 (city/county/township)
        region_name: 区域名称（模糊匹配，可选，向后兼容）
        city: 市级过滤（精确匹配）
        county: 县级过滤（精确匹配）
        township: 乡镇级过滤（精确匹配）
        top_k: Number of similar regions to return (1-50)
        metric: Similarity metric ('cosine' or 'jaccard')
        min_similarity: Minimum similarity threshold (0.0-1.0)

    Returns:
        List of similar regions with scores and common characters
    """
    similarity_table, scol = _regional_schema(dbpath, T.REGION_SIMILARITY)
    char_table, ccol = _regional_schema(dbpath, T.CHAR_REGIONAL_ANALYSIS)
    # 构建目标区域查询条件
    target_query = f"""
    SELECT DISTINCT {scol(C.REGION_SIMILARITY.REGION1)} as region_name
    FROM {similarity_table}
    WHERE {scol(C.REGION_SIMILARITY.REGION_LEVEL)} = ?
    """
    params = [normalize_region_level(dbpath, T.REGION_SIMILARITY, region_level)]

    # 优先使用层级参数（精确匹配）
    if city is not None:
        # 需要从char_regional_analysis表获取完整信息
        target_query = f"""
        SELECT DISTINCT {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)} as region_name
        FROM {char_table}
        WHERE {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)} = ? AND {ccol(C.CHAR_REGIONAL_ANALYSIS.CITY)} = ?
        """
        params = [normalize_region_level(dbpath, T.CHAR_REGIONAL_ANALYSIS, region_level), city]

        if county is not None:
            target_query += f" AND {ccol(C.CHAR_REGIONAL_ANALYSIS.COUNTY)} = ?"
            params.append(county)
        elif city is not None and region_level == 'township':
            # Handle 东莞市/中山市 (no county level)
            target_query += f" AND ({ccol(C.CHAR_REGIONAL_ANALYSIS.COUNTY)} IS NULL OR {ccol(C.CHAR_REGIONAL_ANALYSIS.COUNTY)} = '')"

        if township is not None:
            target_query += f" AND {ccol(C.CHAR_REGIONAL_ANALYSIS.TOWNSHIP)} = ?"
            params.append(township)

    # 向后兼容：region_name（模糊匹配）
    elif region_name is not None:
        # 特殊处理：中山市和东莞市没有县级，当 county 级别查询时自动切换到 city 级别
        actual_level = region_level
        if region_level == 'county' and region_name in ['中山市', '东莞市']:
            actual_level = 'city'

        target_query = f"""
        SELECT DISTINCT {scol(C.REGION_SIMILARITY.REGION1)} as region_name
        FROM {similarity_table}
        WHERE {scol(C.REGION_SIMILARITY.REGION_LEVEL)} = ? AND {scol(C.REGION_SIMILARITY.REGION1)} = ?
        """
        params = [normalize_region_level(dbpath, T.REGION_SIMILARITY, actual_level), region_name]
    else:
        raise HTTPException(status_code=400, detail="Must provide either city/county/township or region_name")

    target_rows = execute_query(db, target_query, tuple(params))

    if not target_rows:
        raise HTTPException(status_code=404, detail=f"Target region not found")

    # 如果有多个匹配（重名），返回错误提示
    if len(target_rows) > 1:
        regions = [row['region_name'] for row in target_rows]
        raise HTTPException(
            status_code=400,
            detail=f"Multiple regions found: {regions}. Please specify city/county/township to disambiguate."
        )

    target_region = target_rows[0]['region_name']

    # 确定实际查询的级别（处理中山市/东莞市特殊情况）
    query_level = region_level
    if region_level == 'county' and target_region in ['中山市', '东莞市']:
        query_level = 'city'

    # Determine which similarity column to use
    sim_column = qcolumn(dbpath, T.REGION_SIMILARITY, getattr(SIMILARITY_METRIC_COLUMNS, metric))

    # Query similar regions (check both region1 and region2)
    query = f"""
    SELECT
        CASE
            WHEN {scol(C.REGION_SIMILARITY.REGION1)} = ? THEN {scol(C.REGION_SIMILARITY.REGION2)}
            ELSE {scol(C.REGION_SIMILARITY.REGION1)}
        END as similar_region,
        {sim_column} as similarity,
        {scol(C.REGION_SIMILARITY.COMMON_HIGH_TENDENCY_CHARS)} as common_high_tendency_chars,
        CASE
            WHEN {scol(C.REGION_SIMILARITY.REGION1)} = ? THEN {scol(C.REGION_SIMILARITY.DISTINCTIVE_CHARS_R2)}
            ELSE {scol(C.REGION_SIMILARITY.DISTINCTIVE_CHARS_R1)}
        END as distinctive_chars
    FROM {similarity_table}
    WHERE {scol(C.REGION_SIMILARITY.REGION_LEVEL)} = ?
      AND ({scol(C.REGION_SIMILARITY.REGION1)} = ? OR {scol(C.REGION_SIMILARITY.REGION2)} = ?)
      AND {sim_column} >= ?
    ORDER BY {sim_column} DESC
    LIMIT ?
    """

    rows = execute_query(db, query, (target_region, target_region, normalize_region_level(dbpath, T.REGION_SIMILARITY, query_level), target_region, target_region, min_similarity, top_k))

    if not rows:
        raise HTTPException(status_code=404, detail=f"No similar regions found for '{target_region}'")

    results = []
    for row in rows:
        results.append({
            "region": row["similar_region"],
            "similarity": round(row["similarity"], 4),
            "common_chars": json.loads(row["common_high_tendency_chars"]) if row["common_high_tendency_chars"] else [],
            "distinctive_chars": json.loads(row["distinctive_chars"]) if row["distinctive_chars"] else []
        })

    return {
        "target_region": target_region,
        "region_level": region_level,
        "metric": metric,
        "count": len(results),
        "similar_regions": results
    }


@router.get("/similarity/pair")
async def get_pair_similarity(
    region1: str = Query(..., description="区域1名称"),
    region2: str = Query(..., description="区域2名称"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取两个区域之间的相似度指标(支持跨层级比较)

    Get similarity metrics between two specific regions (supports cross-level comparison).

    Args:
        region1: First region name
        region2: Second region name

    Returns:
        All similarity metrics, common chars, and distinctive chars
    """
    similarity_table, scol = _regional_schema(dbpath, T.REGION_SIMILARITY)
    # 先尝试从预计算表查询(同层级)
    query = f"""
    SELECT
        {scol(C.REGION_SIMILARITY.REGION1)} as region1, {scol(C.REGION_SIMILARITY.REGION2)} as region2, {scol(C.REGION_SIMILARITY.REGION_LEVEL)} as region_level,
        {scol(C.REGION_SIMILARITY.COSINE_SIMILARITY)} as cosine_similarity, {scol(C.REGION_SIMILARITY.JACCARD_SIMILARITY)} as jaccard_similarity, {scol(C.REGION_SIMILARITY.EUCLIDEAN_DISTANCE)} as euclidean_distance,
        {scol(C.REGION_SIMILARITY.COMMON_HIGH_TENDENCY_CHARS)} as common_high_tendency_chars,
        {scol(C.REGION_SIMILARITY.DISTINCTIVE_CHARS_R1)} as distinctive_chars_r1, {scol(C.REGION_SIMILARITY.DISTINCTIVE_CHARS_R2)} as distinctive_chars_r2,
        {scol(C.REGION_SIMILARITY.FEATURE_DIMENSION)} as feature_dimension
    FROM {similarity_table}
    WHERE ({scol(C.REGION_SIMILARITY.REGION1)} = ? AND {scol(C.REGION_SIMILARITY.REGION2)} = ?) OR ({scol(C.REGION_SIMILARITY.REGION1)} = ? AND {scol(C.REGION_SIMILARITY.REGION2)} = ?)
    """

    row = execute_single(db, query, (region1, region2, region2, region1))

    if row:
        # 找到预计算的相似度数据（指标准确，字符列表实时重查全量）
        r1_is_first = (row["region1"] == region1)
        region_level = row["region_level"] if "region_level" in row.keys() else None

        char_table, ccol = _regional_schema(dbpath, T.CHAR_REGIONAL_ANALYSIS)

        def _fetch_freq_dict(region: str, level: str) -> dict:
            """获取区域全量字符频率（用于 common_chars 频率排序）"""
            q = f"""
            SELECT {ccol(C.CHAR_REGIONAL_ANALYSIS.CHAR)} as char, {ccol(C.CHAR_REGIONAL_ANALYSIS.FREQUENCY)} as frequency FROM {char_table}
            WHERE {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)} = ? AND {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)} = ?
            """
            rows = execute_query(db, q, (normalize_region_level(dbpath, T.CHAR_REGIONAL_ANALYSIS, level), region))
            return {r['char']: r['frequency'] for r in rows} if rows else {}

        def _fetch_distinctive(region: str, level: str) -> list:
            """获取高倾向字符（z_score >= 2.0，与批量算法一致）"""
            q = f"""
            SELECT {ccol(C.CHAR_REGIONAL_ANALYSIS.CHAR)} as char FROM {char_table}
            WHERE {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)} = ? AND {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)} = ? AND {ccol(C.CHAR_REGIONAL_ANALYSIS.Z_SCORE)} >= 2.0
            ORDER BY {ccol(C.CHAR_REGIONAL_ANALYSIS.Z_SCORE)} DESC
            """
            rows = execute_query(db, q, (normalize_region_level(dbpath, T.CHAR_REGIONAL_ANALYSIS, level), region))
            return [r['char'] for r in rows] if rows else []

        if region_level:
            freq_r1 = _fetch_freq_dict(region1, region_level)
            freq_r2 = _fetch_freq_dict(region2, region_level)
            # common_chars: 两地都出现的字，按几何均值频率排序（不用 z_score，z_score 是衡量特色的）
            shared = set(freq_r1) & set(freq_r2)
            common_chars = sorted(shared, key=lambda c: freq_r1[c] * freq_r2[c], reverse=True)
            # distinctive_chars: z_score >= 2.0，衡量各地相对其他同级区域的特色
            dist_r1 = set(_fetch_distinctive(region1, region_level))
            dist_r2 = set(_fetch_distinctive(region2, region_level))
            distinctive_r1 = sorted(dist_r1 - dist_r2)
            distinctive_r2 = sorted(dist_r2 - dist_r1)
        else:
            # 回退：使用存储值
            common_chars = json.loads(row["common_high_tendency_chars"]) if row["common_high_tendency_chars"] else []
            dist_r1 = set(json.loads(row["distinctive_chars_r1"]) if row["distinctive_chars_r1"] else [])
            dist_r2 = set(json.loads(row["distinctive_chars_r2"]) if row["distinctive_chars_r2"] else [])
            distinctive_r1 = sorted(dist_r1)
            distinctive_r2 = sorted(dist_r2)

        return {
            "region1": region1,
            "region2": region2,
            "cosine_similarity": round(row["cosine_similarity"], 4),
            "jaccard_similarity": round(row["jaccard_similarity"], 4),
            "euclidean_distance": round(row["euclidean_distance"], 4),
            "common_chars": common_chars,
            "distinctive_chars_r1": distinctive_r1 if r1_is_first else distinctive_r2,
            "distinctive_chars_r2": distinctive_r2 if r1_is_first else distinctive_r1,
            "feature_dimension": row["feature_dimension"],
            "cross_level": False
        }

    # 没有预计算数据,尝试跨层级实时计算
    from fastapi.concurrency import run_in_threadpool
    result = await run_in_threadpool(_compute_cross_level_similarity, db, dbpath, region1, region2)

    if result:
        return result

    # 都找不到
    raise HTTPException(
        status_code=404,
        detail=f"Similarity data not found for regions '{region1}' and '{region2}'"
    )


def _compute_cross_level_similarity(db: sqlite3.Connection, dbpath: str, region1: str, region2: str) -> dict:
    """
    实时计算跨层级区域相似度（使用字符频率向量，与预计算算法一致）

    Args:
        db: 数据库连接
        region1: 区域1名称
        region2: 区域2名称

    Returns:
        相似度结果字典,如果无法计算则返回None
    """
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine, euclidean_distances

    # 1. 获取两个区域的特征
    features1 = _get_region_features(db, dbpath, region1)
    features2 = _get_region_features(db, dbpath, region2)

    if not features1 or not features2:
        return None

    # 2. 构建统一的字符空间（所有字符的并集）
    char_freq1 = features1['char_freq_dict']
    char_freq2 = features2['char_freq_dict']
    all_chars = sorted(set(char_freq1.keys()) | set(char_freq2.keys()))

    # 3. 构建密集向量（按字符顺序）
    vec1 = np.array([char_freq1.get(char, 0.0) for char in all_chars]).reshape(1, -1)
    vec2 = np.array([char_freq2.get(char, 0.0) for char in all_chars]).reshape(1, -1)

    # 4. 计算相似度指标
    # Cosine similarity
    cosine_sim = float(sklearn_cosine(vec1, vec2)[0][0])

    # Euclidean distance
    euclidean_dist = float(euclidean_distances(vec1, vec2)[0][0])

    # Jaccard similarity
    chars1 = set(features1.get('high_tendency_chars', []))
    chars2 = set(features2.get('high_tendency_chars', []))
    is_cross_level = features1['level'] != features2['level']

    if is_cross_level:
        # 跨层级时 z_score 基准不可比（县级 vs 市级），改用频率 top-25% 的字符集
        threshold1 = float(np.percentile(list(char_freq1.values()), 75)) if char_freq1 else 0.0
        threshold2 = float(np.percentile(list(char_freq2.values()), 75)) if char_freq2 else 0.0
        sig_chars1 = {c for c, f in char_freq1.items() if f >= threshold1}
        sig_chars2 = {c for c, f in char_freq2.items() if f >= threshold2}
        union = sig_chars1 | sig_chars2
        jaccard_sim = len(sig_chars1 & sig_chars2) / len(union) if union else 0.0
    else:
        # 同层级：沿用 z_score 高倾向字符，与批量预计算算法一致
        union = chars1 | chars2
        jaccard_sim = len(chars1 & chars2) / len(union) if union else 0.0

    # 5. 找出共同字符和特征字符
    # common_chars: 跨层级时 z_score 基准不同（县级 vs 市级），直接取交集无意义
    # 改用原始频率重叠：两个区域都出现的字，按几何均值降序排列
    shared_chars = set(char_freq1.keys()) & set(char_freq2.keys())
    common_chars = sorted(
        shared_chars,
        key=lambda c: char_freq1[c] * char_freq2[c],
        reverse=True
    )
    # distinctive_chars: z_score 在各自层级内有意义，保持不变
    distinctive_chars1 = list(chars1 - chars2)
    distinctive_chars2 = list(chars2 - chars1)

    return {
        "region1": region1,
        "region2": region2,
        "region1_level": features1['level'],
        "region2_level": features2['level'],
        "cosine_similarity": round(cosine_sim, 4),
        "jaccard_similarity": round(jaccard_sim, 4),
        "euclidean_distance": round(euclidean_dist, 4),
        "common_chars": common_chars,
        "distinctive_chars_r1": distinctive_chars1,
        "distinctive_chars_r2": distinctive_chars2,
        "feature_dimension": len(all_chars),
        "cross_level": is_cross_level,
        "computed_realtime": True
    }


def _get_region_features(db: sqlite3.Connection, dbpath: str, region_name: str) -> dict:
    """
    获取区域特征向量（基于字符频率，与预计算算法一致）

    Args:
        db: 数据库连接
        region_name: 区域名称

    Returns:
        包含特征向量和元数据的字典,如果找不到则返回None
    """
    char_table, ccol = _regional_schema(dbpath, T.CHAR_REGIONAL_ANALYSIS)

    # 检测区域层级
    detected_level = None
    for level_value in ('city', 'county', 'township'):
        # 尝试查询该层级是否有数据
        query = f"""
        SELECT COUNT(*) as cnt
        FROM {char_table}
        WHERE {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)} = ? AND {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)} = ?
        """
        row = execute_single(db, query, (normalize_region_level(dbpath, T.CHAR_REGIONAL_ANALYSIS, level_value), region_name))
        if row and row['cnt'] > 0:
            detected_level = level_value
            break

    if not detected_level:
        return None

    # 获取该区域的所有字符频率数据
    query = f"""
    SELECT {ccol(C.CHAR_REGIONAL_ANALYSIS.CHAR)} as char, {ccol(C.CHAR_REGIONAL_ANALYSIS.FREQUENCY)} as frequency
    FROM {char_table}
    WHERE {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)} = ? AND {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)} = ?
    ORDER BY {ccol(C.CHAR_REGIONAL_ANALYSIS.CHAR)}
    """
    rows = execute_query(db, query, (normalize_region_level(dbpath, T.CHAR_REGIONAL_ANALYSIS, detected_level), region_name))

    if not rows:
        return None

    # 构建字符频率向量（字典形式，稀疏表示）
    char_freq_dict = {row['char']: row['frequency'] for row in rows}

    # 获取高倾向字符（用于 Jaccard 计算）
    high_tendency_chars = _get_high_tendency_chars(db, dbpath, region_name, detected_level)

    return {
        'region_name': region_name,
        'level': detected_level,
        'char_freq_dict': char_freq_dict,  # 稀疏表示
        'high_tendency_chars': high_tendency_chars
    }


def _get_high_tendency_chars(db: sqlite3.Connection, dbpath: str, region_name: str, level: str) -> list:
    """
    获取区域的高倾向字符

    Args:
        db: 数据库连接
        region_name: 区域名称
        level: 区域层级

    Returns:
        高倾向字符列表
    """
    char_table, ccol = _regional_schema(dbpath, T.CHAR_REGIONAL_ANALYSIS)
    query = f"""
    SELECT {ccol(C.CHAR_REGIONAL_ANALYSIS.CHAR)} as char
    FROM {char_table}
    WHERE {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_LEVEL)} = ? AND {ccol(C.CHAR_REGIONAL_ANALYSIS.REGION_NAME)} = ?
    ORDER BY {ccol(C.CHAR_REGIONAL_ANALYSIS.Z_SCORE)} DESC
    """

    rows = execute_query(db, query, (normalize_region_level(dbpath, T.CHAR_REGIONAL_ANALYSIS, level), region_name))
    return [row['char'] for row in rows] if rows else []


@router.get("/similarity/matrix")
async def get_similarity_matrix(
    regions: Optional[str] = Query(None, description="逗号分隔的区域名称列表"),
    metric: str = Query("cosine", regex="^(cosine|jaccard)$", description="相似度指标"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取多个区域的相似度矩阵（支持跨层级）

    Get similarity matrix for multiple regions (supports cross-level comparison).

    Args:
        regions: Comma-separated region names (optional, default: top 20 by village count)
        metric: Similarity metric ('cosine' or 'jaccard')

    Returns:
        Similarity matrix as 2D array with region labels
    """
    from fastapi.concurrency import run_in_threadpool

    # Get region list
    if regions:
        region_list = [r.strip() for r in regions.split(',')]
    else:
        # Get top 20 regions by village count
        villages_table, vcol = _regional_schema(dbpath, T.VILLAGES)
        county_col = vcol("county")
        query = f"""
        SELECT {county_col} as region_name, COUNT(*) as count
        FROM {villages_table}
        GROUP BY {county_col}
        ORDER BY count DESC
        LIMIT 20
        """
        rows = execute_query(db, query)
        region_list = [row["region_name"] for row in rows]

    if not region_list:
        raise HTTPException(status_code=400, detail="No regions specified")

    # Detect region levels
    region_levels = {}
    for region in region_list:
        features = _get_region_features(db, dbpath, region)
        if features:
            region_levels[region] = features['level']
        else:
            raise HTTPException(status_code=404, detail=f"Region '{region}' not found")

    # Build similarity matrix
    n = len(region_list)
    matrix = [[0.0] * n for _ in range(n)]
    similarity_metric_column = getattr(SIMILARITY_METRIC_COLUMNS, metric)
    sim_column = qcolumn(dbpath, T.REGION_SIMILARITY, similarity_metric_column)
    sim_col_name = column_name(dbpath, T.REGION_SIMILARITY, similarity_metric_column)
    similarity_table, scol = _regional_schema(dbpath, T.REGION_SIMILARITY)

    for i, r1 in enumerate(region_list):
        for j, r2 in enumerate(region_list):
            if i == j:
                matrix[i][j] = 1.0
            elif i < j:
                # Check if same level or cross-level
                same_level = region_levels[r1] == region_levels[r2]

                if same_level:
                    # Try pre-computed data first
                    query = f"""
                    SELECT {sim_column}
                    FROM {similarity_table}
                    WHERE ({scol(C.REGION_SIMILARITY.REGION1)} = ? AND {scol(C.REGION_SIMILARITY.REGION2)} = ?) OR ({scol(C.REGION_SIMILARITY.REGION1)} = ? AND {scol(C.REGION_SIMILARITY.REGION2)} = ?)
                    """
                    row = execute_single(db, query, (r1, r2, r2, r1))
                    if row:
                        matrix[i][j] = round(row[sim_col_name], 4)
                        matrix[j][i] = round(row[sim_col_name], 4)
                        continue

                # Cross-level or no pre-computed data: compute in real-time
                result = await run_in_threadpool(_compute_cross_level_similarity, db, dbpath, r1, r2)
                if result:
                    sim_value = result[f"{metric}_similarity"]
                    matrix[i][j] = round(sim_value, 4)
                    matrix[j][i] = round(sim_value, 4)

    return {
        "regions": region_list,
        "region_levels": region_levels,
        "metric": metric,
        "matrix": matrix,
        "cross_level": len(set(region_levels.values())) > 1
    }


@router.get("/list")
async def list_regions(
    region_level: str = Query("county", description="区域级别"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取所有可用区域列表

    Get list of all available regions.

    Args:
        region_level: Region level (default: 'county')

    Returns:
        List of region names with village counts
    """
    villages_table, vcol = _regional_schema(dbpath, T.VILLAGES)
    level_map = {
        "city": vcol("city"),
        "county": vcol("county"),
        "township": vcol("township")
    }

    column = level_map.get(region_level, vcol("county"))

    query = f"""
    SELECT {column} as region_name, COUNT(*) as village_count
    FROM {villages_table}
    GROUP BY {column}
    ORDER BY village_count DESC
    """

    rows = execute_query(db, query)

    return {
        "region_level": region_level,
        "count": len(rows),
        "regions": [
            {"region_name": row["region_name"], "village_count": row["village_count"]}
            for row in rows
        ]
    }
