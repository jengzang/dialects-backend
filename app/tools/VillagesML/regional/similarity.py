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
    获取两个区域之间的相似度指标

    Get similarity metrics between two specific regions.

    Args:
        region1: First region name
        region2: Second region name

    Returns:
        All similarity metrics, common chars, and distinctive chars
    """
    # Query (handle both orderings)
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

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Similarity data not found for regions '{region1}' and '{region2}'"
        )

    # Determine correct ordering
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
        "feature_dimension": row["feature_dimension"]
    }


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
