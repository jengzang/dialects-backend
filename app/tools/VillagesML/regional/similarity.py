"""
Region Similarity API Endpoints

Provides endpoints for querying region similarity metrics.
Phase 15: 区域相似度分析
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
import sqlite3
import json

from ..dependencies import get_db, execute_query, execute_single

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("/similarity/search")
async def search_similar_regions(
    region: str = Query(..., description="目标区域名称"),
    top_k: int = Query(10, ge=1, le=50, description="返回相似区域数量"),
    metric: str = Query("cosine", regex="^(cosine|jaccard)$", description="相似度指标"),
    min_similarity: float = Query(0.0, ge=0.0, le=1.0, description="最小相似度阈值"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    查找与目标区域相似的其他区域

    Find regions similar to a target region.

    Args:
        region: Target region name
        top_k: Number of similar regions to return (1-50)
        metric: Similarity metric ('cosine' or 'jaccard')
        min_similarity: Minimum similarity threshold (0.0-1.0)

    Returns:
        List of similar regions with scores and common characters
    """
    # Determine which similarity column to use
    sim_column = f"{metric}_similarity"

    # Query similar regions (check both region1 and region2)
    query = f"""
    SELECT
        CASE
            WHEN region1 = ? THEN region2
            ELSE region1
        END as similar_region,
        {sim_column} as similarity,
        common_high_tendency_chars,
        CASE
            WHEN region1 = ? THEN distinctive_chars_r2
            ELSE distinctive_chars_r1
        END as distinctive_chars
    FROM region_similarity
    WHERE (region1 = ? OR region2 = ?)
    AND {sim_column} >= ?
    ORDER BY {sim_column} DESC
    LIMIT ?
    """

    rows = execute_query(db, query, (region, region, region, region, min_similarity, top_k))

    if not rows:
        raise HTTPException(status_code=404, detail=f"Region '{region}' not found or no similar regions")

    results = []
    for row in rows:
        results.append({
            "region": row["similar_region"],
            "similarity": round(row["similarity"], 4),
            "common_chars": json.loads(row["common_high_tendency_chars"]) if row["common_high_tendency_chars"] else [],
            "distinctive_chars": json.loads(row["distinctive_chars"]) if row["distinctive_chars"] else []
        })

    return {
        "target_region": region,
        "metric": metric,
        "count": len(results),
        "similar_regions": results
    }


@router.get("/similarity/pair")
async def get_pair_similarity(
    region1: str = Query(..., description="区域1名称"),
    region2: str = Query(..., description="区域2名称"),
    db: sqlite3.Connection = Depends(get_db)
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
    # 先尝试从预计算表查询(同层级)
    query = """
    SELECT
        region1, region2,
        cosine_similarity, jaccard_similarity, euclidean_distance,
        common_high_tendency_chars,
        distinctive_chars_r1, distinctive_chars_r2,
        feature_dimension
    FROM region_similarity
    WHERE (region1 = ? AND region2 = ?) OR (region1 = ? AND region2 = ?)
    """

    row = execute_single(db, query, (region1, region2, region2, region1))

    if row:
        # 找到预计算的相似度数据
        r1_is_first = (row["region1"] == region1)

        return {
            "region1": region1,
            "region2": region2,
            "cosine_similarity": round(row["cosine_similarity"], 4),
            "jaccard_similarity": round(row["jaccard_similarity"], 4),
            "euclidean_distance": round(row["euclidean_distance"], 4),
            "common_chars": json.loads(row["common_high_tendency_chars"]) if row["common_high_tendency_chars"] else [],
            "distinctive_chars_r1": json.loads(row["distinctive_chars_r1"] if r1_is_first else row["distinctive_chars_r2"]) if row["distinctive_chars_r1"] else [],
            "distinctive_chars_r2": json.loads(row["distinctive_chars_r2"] if r1_is_first else row["distinctive_chars_r1"]) if row["distinctive_chars_r2"] else [],
            "feature_dimension": row["feature_dimension"],
            "cross_level": False
        }

    # 没有预计算数据,尝试跨层级实时计算
    from fastapi.concurrency import run_in_threadpool
    result = await run_in_threadpool(_compute_cross_level_similarity, db, region1, region2)

    if result:
        return result

    # 都找不到
    raise HTTPException(
        status_code=404,
        detail=f"Similarity data not found for regions '{region1}' and '{region2}'"
    )


def _compute_cross_level_similarity(db: sqlite3.Connection, region1: str, region2: str) -> dict:
    """
    实时计算跨层级区域相似度

    Args:
        db: 数据库连接
        region1: 区域1名称
        region2: 区域2名称

    Returns:
        相似度结果字典,如果无法计算则返回None
    """
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine
    from sklearn.metrics import jaccard_score

    # 1. 检测区域层级并获取特征
    features1 = _get_region_features(db, region1)
    features2 = _get_region_features(db, region2)

    if not features1 or not features2:
        return None

    # 2. 计算相似度
    # Cosine similarity
    vec1 = np.array(features1['feature_vector']).reshape(1, -1)
    vec2 = np.array(features2['feature_vector']).reshape(1, -1)
    cosine_sim = float(sklearn_cosine(vec1, vec2)[0][0])

    # Euclidean distance
    euclidean_dist = float(np.linalg.norm(vec1 - vec2))

    # Jaccard similarity (基于高倾向字符)
    chars1 = set(features1.get('high_tendency_chars', []))
    chars2 = set(features2.get('high_tendency_chars', []))
    if chars1 or chars2:
        jaccard_sim = len(chars1 & chars2) / len(chars1 | chars2) if (chars1 | chars2) else 0.0
    else:
        jaccard_sim = 0.0

    # 3. 找出共同字符和特征字符
    common_chars = list(chars1 & chars2)[:10]
    distinctive_chars1 = list(chars1 - chars2)[:10]
    distinctive_chars2 = list(chars2 - chars1)[:10]

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
        "feature_dimension": len(features1['feature_vector']),
        "cross_level": features1['level'] != features2['level'],
        "computed_realtime": True
    }


def _get_region_features(db: sqlite3.Connection, region_name: str) -> dict:
    """
    获取区域特征向量

    Args:
        db: 数据库连接
        region_name: 区域名称

    Returns:
        包含特征向量和元数据的字典,如果找不到则返回None
    """
    # 尝试从不同层级的聚合表查询
    tables = [
        ('city_aggregates', 'city', 'city'),
        ('county_aggregates', 'county', 'county'),
        ('town_aggregates', 'town', 'township')
    ]

    for table_name, column_name, level in tables:
        query = f"""
        SELECT
            {column_name},
            sem_mountain_pct, sem_water_pct, sem_settlement_pct,
            sem_direction_pct, sem_clan_pct, sem_symbolic_pct,
            sem_agriculture_pct, sem_vegetation_pct, sem_infrastructure_pct,
            avg_name_length, total_villages
        FROM {table_name}
        WHERE {column_name} = ?
        """

        row = execute_single(db, query, (region_name,))

        if row:
            # 构建特征向量
            feature_vector = [
                row.get('sem_mountain_pct', 0) or 0,
                row.get('sem_water_pct', 0) or 0,
                row.get('sem_settlement_pct', 0) or 0,
                row.get('sem_direction_pct', 0) or 0,
                row.get('sem_clan_pct', 0) or 0,
                row.get('sem_symbolic_pct', 0) or 0,
                row.get('sem_agriculture_pct', 0) or 0,
                row.get('sem_vegetation_pct', 0) or 0,
                row.get('sem_infrastructure_pct', 0) or 0,
                row.get('avg_name_length', 0) or 0,
                row.get('total_villages', 0) or 0
            ]

            # 获取高倾向字符
            high_tendency_chars = _get_high_tendency_chars(db, region_name, level)

            return {
                'region_name': region_name,
                'level': level,
                'feature_vector': feature_vector,
                'high_tendency_chars': high_tendency_chars
            }

    return None


def _get_high_tendency_chars(db: sqlite3.Connection, region_name: str, level: str) -> list:
    """
    获取区域的高倾向字符

    Args:
        db: 数据库连接
        region_name: 区域名称
        level: 区域层级

    Returns:
        高倾向字符列表
    """
    query = """
    SELECT char
    FROM char_regional_analysis
    WHERE region_level = ? AND region_name = ?
    ORDER BY z_score DESC
    LIMIT 20
    """

    rows = execute_query(db, query, (level, region_name))
    return [row['char'] for row in rows] if rows else []


@router.get("/similarity/matrix")
async def get_similarity_matrix(
    regions: Optional[str] = Query(None, description="逗号分隔的区域名称列表"),
    metric: str = Query("cosine", regex="^(cosine|jaccard)$", description="相似度指标"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取多个区域的相似度矩阵

    Get similarity matrix for multiple regions.

    Args:
        regions: Comma-separated region names (optional, default: top 20 by village count)
        metric: Similarity metric ('cosine' or 'jaccard')

    Returns:
        Similarity matrix as 2D array with region labels
    """
    # Get region list
    if regions:
        region_list = [r.strip() for r in regions.split(',')]
    else:
        # Get top 20 regions by village count
        query = """
        SELECT 区县级 as region_name, COUNT(*) as count
        FROM 广东省自然村_预处理
        GROUP BY 区县级
        ORDER BY count DESC
        LIMIT 20
        """
        rows = execute_query(db, query)
        region_list = [row["region_name"] for row in rows]

    if not region_list:
        raise HTTPException(status_code=400, detail="No regions specified")

    # Build similarity matrix
    n = len(region_list)
    matrix = [[0.0] * n for _ in range(n)]

    sim_column = f"{metric}_similarity"

    for i, r1 in enumerate(region_list):
        for j, r2 in enumerate(region_list):
            if i == j:
                matrix[i][j] = 1.0
            elif i < j:
                # Query database
                query = f"""
                SELECT {sim_column}
                FROM region_similarity
                WHERE (region1 = ? AND region2 = ?) OR (region1 = ? AND region2 = ?)
                """
                row = execute_single(db, query, (r1, r2, r2, r1))
                if row:
                    matrix[i][j] = round(row[sim_column], 4)
                    matrix[j][i] = round(row[sim_column], 4)

    return {
        "regions": region_list,
        "metric": metric,
        "matrix": matrix
    }


@router.get("/list")
async def list_regions(
    region_level: str = Query("county", description="区域级别"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取所有可用区域列表

    Get list of all available regions.

    Args:
        region_level: Region level (default: 'county')

    Returns:
        List of region names with village counts
    """
    # Map region_level to column name
    level_map = {
        "city": "市级",
        "county": "区县级",
        "township": "乡镇级"
    }

    column = level_map.get(region_level, "区县级")

    query = f"""
    SELECT {column} as region_name, COUNT(*) as village_count
    FROM 广东省自然村_预处理
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
