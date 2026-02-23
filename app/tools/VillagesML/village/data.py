"""
村庄级别数据API
Village-level Data API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, execute_query, execute_single
from ..run_id_manager import run_id_manager

router = APIRouter(prefix="/village", tags=["village-data"])


@router.get("/ngrams/{village_id}")
def get_village_ngrams(
    village_id: int,
    n: Optional[int] = Query(None, ge=2, le=4, description="N-gram长度"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取特定村庄的N-gram
    Get n-grams for a specific village

    Args:
        village_id: 村庄ID (ROWID from main table)
        n: N-gram长度（2-4）

    Returns:
        dict: 村庄N-gram信息
    """
    # First get village name from main table using ROWID
    village_query = """
        SELECT "自然村" as village_name, "村委会" as village_committee
        FROM "广东省自然村"
        WHERE ROWID = ?
    """
    village_info = execute_single(db, village_query, (village_id,))

    if not village_info:
        raise HTTPException(
            status_code=404,
            detail=f"Village {village_id} not found"
        )

    # Then query ngrams table using village name and committee
    query = """
        SELECT
            "村委会" as village_committee,
            "自然村" as village_name,
            bigrams,
            trigrams,
            prefix_bigram,
            suffix_bigram
        FROM village_ngrams
        WHERE "自然村" = ? AND "村委会" = ?
    """

    result = execute_single(db, query, (village_info['village_name'], village_info['village_committee']))

    if not result:
        # Return empty structure if no ngram data exists for this village
        return {
            "village_committee": village_info['village_committee'],
            "village_name": village_info['village_name'],
            "bigrams": None,
            "trigrams": None,
            "prefix_bigram": None,
            "suffix_bigram": None
        }

    # Filter by n if specified
    if n is not None:
        if n == 2:
            result = {k: v for k, v in result.items() if k in ['village_committee', 'village_name', 'bigrams', 'prefix_bigram', 'suffix_bigram']}
        elif n == 3:
            result = {k: v for k, v in result.items() if k in ['village_committee', 'village_name', 'trigrams']}
        elif n == 4:
            # No quadgrams in actual schema
            result = {k: v for k, v in result.items() if k in ['village_committee', 'village_name']}

    return result


@router.get("/semantic-structure/{village_id}")
def get_village_semantic_structure(
    village_id: int,
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取特定村庄的语义结构
    Get semantic structure for a specific village

    Args:
        village_id: 村庄ID (ROWID from main table)

    Returns:
        dict: 村庄语义结构
    """
    # First get village name from main table using ROWID
    village_query = """
        SELECT "自然村" as village_name, "村委会" as village_committee
        FROM "广东省自然村"
        WHERE ROWID = ?
    """
    village_info = execute_single(db, village_query, (village_id,))

    if not village_info:
        raise HTTPException(
            status_code=404,
            detail=f"Village {village_id} not found"
        )

    # Then query semantic structure table
    query = """
        SELECT
            "村委会" as village_committee,
            "自然村" as village_name,
            semantic_sequence,
            sequence_length,
            has_modifier,
            has_head,
            has_settlement
        FROM village_semantic_structure
        WHERE "自然村" = ? AND "村委会" = ?
    """

    result = execute_single(db, query, (village_info['village_name'], village_info['village_committee']))

    if not result:
        # Return empty structure if no semantic data exists for this village
        return {
            "village_committee": village_info['village_committee'],
            "village_name": village_info['village_name'],
            "semantic_sequence": None,
            "sequence_length": None,
            "has_modifier": None,
            "has_head": None,
            "has_settlement": None
        }

    return result


@router.get("/features/{village_id}")
def get_village_features(
    village_id: int,
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取特定村庄的特征向量
    Get feature vector for a specific village

    Args:
        village_id: 村庄ID (ROWID from main table)
        run_id: 分析运行ID

    Returns:
        dict: 村庄特征
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("village_features")

    # First get village info from main table using ROWID
    village_query = """
        SELECT "自然村" as village_name, "市级" as city, "区县级" as county
        FROM "广东省自然村"
        WHERE ROWID = ?
    """
    village_info = execute_single(db, village_query, (village_id,))

    if not village_info:
        raise HTTPException(
            status_code=404,
            detail=f"Village {village_id} not found"
        )

    # Then query features table
    query = """
        SELECT *
        FROM village_features
        WHERE village_name = ? AND city = ? AND county = ? AND run_id = ?
    """

    result = execute_single(db, query, (
        village_info['village_name'],
        village_info['city'],
        village_info['county'],
        run_id
    ))

    if not result:
        # Return empty dict if no feature data exists for this village
        return {
            "message": "No feature data available for this village",
            "village_name": village_info['village_name'],
            "city": village_info['city'],
            "county": village_info['county']
        }

    return result


@router.get("/spatial-features/{village_id}")
def get_village_spatial_features(
    village_id: int,
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取特定村庄的空间特征
    Get spatial features for a specific village

    Args:
        village_id: 村庄ID (ROWID from main table)
        run_id: 分析运行ID

    Returns:
        dict: 村庄空间特征
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("village_features")

    # spatial_features table has village_id column, so we can query directly
    query = """
        SELECT
            village_id,
            village_name,
            city,
            county,
            town,
            longitude,
            latitude,
            nn_distance_1,
            nn_distance_5,
            nn_distance_10,
            local_density_1km,
            local_density_5km,
            local_density_10km,
            isolation_score,
            is_isolated,
            spatial_cluster_id,
            cluster_size
        FROM village_spatial_features
        WHERE village_id = ? AND run_id = ?
    """

    result = execute_single(db, query, (str(village_id), run_id))

    if not result:
        # Return empty dict if no spatial feature data exists
        return {
            "message": "No spatial feature data available for this village",
            "village_id": str(village_id)
        }

    return result


@router.get("/complete/{village_id}")
def get_village_complete_profile(
    village_id: int,
    run_id: Optional[str] = Query(None, description="分析运行ID（留空使用活跃版本）"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    获取村庄的完整档案（所有数据）
    Get complete profile for a village (all available data)

    Args:
        village_id: 村庄ID (ROWID from main table)
        run_id: 分析运行ID

    Returns:
        dict: 村庄完整档案
    """
    # 如果未指定run_id，使用活跃版本
    if run_id is None:
        run_id = run_id_manager.get_active_run_id("village_features")

    # Get basic info from main table using ROWID
    basic_query = """
        SELECT
            ROWID as village_id,
            "自然村" as village_name,
            "市级" as city,
            "区县级" as county,
            "乡镇级" as township,
            "村委会" as village_committee,
            "拼音" as pinyin,
            CAST(longitude AS REAL) as longitude,
            CAST(latitude AS REAL) as latitude
        FROM "广东省自然村"
        WHERE ROWID = ?
    """
    basic_info = execute_single(db, basic_query, (village_id,))

    if not basic_info:
        raise HTTPException(
            status_code=404,
            detail=f"Village {village_id} not found"
        )

    # Get spatial features (has village_id column)
    spatial_query = """
        SELECT *
        FROM village_spatial_features
        WHERE village_id = ? AND run_id = ?
    """
    spatial_features = execute_single(db, spatial_query, (str(village_id), run_id))

    # Get semantic structure (uses village_name + committee)
    semantic_query = """
        SELECT *
        FROM village_semantic_structure
        WHERE "自然村" = ? AND "村委会" = ?
    """
    semantic_structure = execute_single(db, semantic_query, (
        basic_info['village_name'],
        basic_info['village_committee']
    ))

    # Get n-grams (uses village_name + committee)
    ngrams_query = """
        SELECT *
        FROM village_ngrams
        WHERE "自然村" = ? AND "村委会" = ?
    """
    ngrams = execute_single(db, ngrams_query, (
        basic_info['village_name'],
        basic_info['village_committee']
    ))

    # Get features (uses village_name + city + county)
    features_query = """
        SELECT *
        FROM village_features
        WHERE village_name = ? AND city = ? AND county = ? AND run_id = ?
    """
    features = execute_single(db, features_query, (
        basic_info['village_name'],
        basic_info['city'],
        basic_info['county'],
        run_id
    ))

    return {
        "basic_info": basic_info,
        "spatial_features": spatial_features,
        "semantic_structure": semantic_structure,
        "ngrams": ngrams,
        "features": features
    }
