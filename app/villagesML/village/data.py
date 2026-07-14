"""
村庄级别数据API
Village-level Data API endpoints
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Optional
import sqlite3

from ..dependencies import get_db, get_dbpath, execute_query, execute_single
from ..run_id_manager import get_run_id_manager
from ..schema_runtime import qcolumn, qtable, run_id_analysis_type
from ..schema_keys import C, T

router = APIRouter(prefix="/village")


@router.get("/ngrams/{village_id}")
def get_village_ngrams(
    village_id: int,
    n: Optional[int] = Query(None, ge=2, le=4, description="N-gram长度"),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
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
    villages_table = qtable(dbpath, T.VILLAGES)
    villages_rowid = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.ROWID)
    villages_name = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.NAME)
    villages_committee = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COMMITTEE)
    ngrams_table = qtable(dbpath, T.VILLAGE_NGRAMS)
    ngrams_name = qcolumn(dbpath, T.VILLAGE_NGRAMS, C.VILLAGE_NGRAMS.NAME)
    ngrams_committee = qcolumn(dbpath, T.VILLAGE_NGRAMS, C.VILLAGE_NGRAMS.COMMITTEE)
    ngrams_bigrams = qcolumn(dbpath, T.VILLAGE_NGRAMS, C.VILLAGE_NGRAMS.BIGRAMS)
    ngrams_trigrams = qcolumn(dbpath, T.VILLAGE_NGRAMS, C.VILLAGE_NGRAMS.TRIGRAMS)
    ngrams_prefix_bigram = qcolumn(dbpath, T.VILLAGE_NGRAMS, C.VILLAGE_NGRAMS.PREFIX_BIGRAM)
    ngrams_suffix_bigram = qcolumn(dbpath, T.VILLAGE_NGRAMS, C.VILLAGE_NGRAMS.SUFFIX_BIGRAM)

    # First get village name from preprocessed table using ROWID
    village_query = f"""
        SELECT {villages_name} as village_name, {villages_committee} as village_committee
        FROM {villages_table}
        WHERE {villages_rowid} = ?
    """
    village_info = execute_single(db, village_query, (village_id,))

    if not village_info:
        raise HTTPException(
            status_code=404,
            detail=f"Village {village_id} not found"
        )

    # Then query ngrams table using village name and committee
    # Try exact match first
    query = f"""
        SELECT
            {ngrams_committee} as village_committee,
            {ngrams_name} as village_name,
            {ngrams_bigrams} as bigrams,
            {ngrams_trigrams} as trigrams,
            {ngrams_prefix_bigram} as prefix_bigram,
            {ngrams_suffix_bigram} as suffix_bigram
        FROM {ngrams_table}
        WHERE {ngrams_name} = ? AND {ngrams_committee} = ?
    """

    result = execute_single(db, query, (village_info['village_name'], village_info['village_committee']))

    # If no result, try matching by village_name only (committee might differ)
    if not result:
        query = f"""
            SELECT
                {ngrams_committee} as village_committee,
                {ngrams_name} as village_name,
                {ngrams_bigrams} as bigrams,
                {ngrams_trigrams} as trigrams,
                {ngrams_prefix_bigram} as prefix_bigram,
                {ngrams_suffix_bigram} as suffix_bigram
            FROM {ngrams_table}
            WHERE {ngrams_name} = ?
        """
        result = execute_single(db, query, (village_info['village_name'],))

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
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取特定村庄的语义结构
    Get semantic structure for a specific village

    Args:
        village_id: 村庄ID (ROWID from main table)

    Returns:
        dict: 村庄语义结构
    """
    villages_table = qtable(dbpath, T.VILLAGES)
    villages_rowid = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.ROWID)
    villages_name = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.NAME)
    villages_committee = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COMMITTEE)
    semantic_table = qtable(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE)
    semantic_name = qcolumn(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE, C.VILLAGE_SEMANTIC_STRUCTURE.NAME)
    semantic_committee = qcolumn(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE, C.VILLAGE_SEMANTIC_STRUCTURE.COMMITTEE)
    semantic_sequence = qcolumn(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE, C.VILLAGE_SEMANTIC_STRUCTURE.SEMANTIC_SEQUENCE)
    sequence_length = qcolumn(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE, C.VILLAGE_SEMANTIC_STRUCTURE.SEQUENCE_LENGTH)
    has_modifier = qcolumn(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE, C.VILLAGE_SEMANTIC_STRUCTURE.HAS_MODIFIER)
    has_head = qcolumn(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE, C.VILLAGE_SEMANTIC_STRUCTURE.HAS_HEAD)
    has_settlement = qcolumn(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE, C.VILLAGE_SEMANTIC_STRUCTURE.HAS_SETTLEMENT)

    # First get village name from preprocessed table using ROWID
    village_query = f"""
        SELECT {villages_name} as village_name, {villages_committee} as village_committee
        FROM {villages_table}
        WHERE {villages_rowid} = ?
    """
    village_info = execute_single(db, village_query, (village_id,))

    if not village_info:
        raise HTTPException(
            status_code=404,
            detail=f"Village {village_id} not found"
        )

    # Then query semantic structure table
    # Try exact match first
    query = f"""
        SELECT
            {semantic_committee} as village_committee,
            {semantic_name} as village_name,
            {semantic_sequence} as semantic_sequence,
            {sequence_length} as sequence_length,
            {has_modifier} as has_modifier,
            {has_head} as has_head,
            {has_settlement} as has_settlement
        FROM {semantic_table}
        WHERE {semantic_name} = ? AND {semantic_committee} = ?
    """

    result = execute_single(db, query, (village_info['village_name'], village_info['village_committee']))

    # If no result, try matching by village_name only (committee might differ)
    if not result:
        query = f"""
            SELECT
                {semantic_committee} as village_committee,
                {semantic_name} as village_name,
                {semantic_sequence} as semantic_sequence,
                {sequence_length} as sequence_length,
                {has_modifier} as has_modifier,
                {has_head} as has_head,
                {has_settlement} as has_settlement
            FROM {semantic_table}
            WHERE {semantic_name} = ?
        """
        result = execute_single(db, query, (village_info['village_name'],))

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
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取特定村庄的特征向量
    Get feature vector for a specific village

    Args:
        village_id: 村庄ID (ROWID from main table)

    Returns:
        dict: 村庄特征
    """
    villages_table = qtable(dbpath, T.VILLAGES)
    villages_rowid = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.ROWID)
    villages_name = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.NAME)
    villages_city = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.CITY)
    villages_county = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COUNTY)
    villages_id = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.VILLAGE_ID)
    features_table = qtable(dbpath, T.VILLAGE_FEATURES)
    features_village_id = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.VILLAGE_ID)

    # First get village info from preprocessed table using ROWID
    village_query = f"""
        SELECT {villages_name} as village_name, {villages_city} as city, {villages_county} as county, {villages_id} as village_id
        FROM {villages_table}
        WHERE {villages_rowid} = ?
    """
    village_info = execute_single(db, village_query, (village_id,))

    if not village_info:
        raise HTTPException(
            status_code=404,
            detail=f"Village {village_id} not found"
        )

    # Then query features table using village_id
    query = f"""
        SELECT *
        FROM {features_table}
        WHERE {features_village_id} = ?
    """

    result = execute_single(db, query, (village_info['village_id'],))

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
    clustering_version: Optional[str] = Query(
        None,
        description="聚类版本ID（留空使用活跃版本）"
    ),
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取特定村庄的空间特征
    Get spatial features for a specific village

    Args:
        village_id: 村庄ID (ROWID from main table)
        clustering_version: 聚类版本ID，默认使用活跃版本

    Returns:
        dict: 村庄空间特征
    """
    if clustering_version is None:
        clustering_version = get_run_id_manager(dbpath).get_active_run_id(
            run_id_analysis_type(dbpath, T.SPATIAL_CLUSTERS)
        )

    villages_table = qtable(dbpath, T.VILLAGES)
    villages_rowid = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.ROWID)
    villages_id = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.VILLAGE_ID)
    spatial_features_table = qtable(dbpath, T.VILLAGE_SPATIAL_FEATURES)
    spatial_features_village_id = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.VILLAGE_ID)
    cluster_assignments_table = qtable(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS)
    cluster_assignments_village_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.VILLAGE_ID)
    cluster_assignments_run_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.RUN_ID)
    cluster_assignments_cluster_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.CLUSTER_ID)
    spatial_clusters_table = qtable(dbpath, T.SPATIAL_CLUSTERS)
    spatial_clusters_run_id = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.RUN_ID)
    spatial_clusters_cluster_id = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CLUSTER_ID)
    spatial_clusters_cluster_size = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CLUSTER_SIZE)

    # First get village_id from preprocessed table
    village_query = f"""
        SELECT {villages_id} as village_id
        FROM {villages_table}
        WHERE {villages_rowid} = ?
    """
    village_info = execute_single(db, village_query, (village_id,))

    if not village_info:
        raise HTTPException(
            status_code=404,
            detail=f"Village {village_id} not found"
        )

    # spatial_features table has village_id column, so we can query directly
    query = f"""
        SELECT
            vsf.{spatial_features_village_id} as village_id,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.VILLAGE_NAME)} as village_name,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.CITY)} as city,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.COUNTY)} as county,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.TOWN)} as town,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.LONGITUDE)} as longitude,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.LATITUDE)} as latitude,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.NN_DISTANCE_1)} as nn_distance_1,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.NN_DISTANCE_5)} as nn_distance_5,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.NN_DISTANCE_10)} as nn_distance_10,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.LOCAL_DENSITY_1KM)} as local_density_1km,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.LOCAL_DENSITY_5KM)} as local_density_5km,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.LOCAL_DENSITY_10KM)} as local_density_10km,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.ISOLATION_SCORE)} as isolation_score,
            vsf.{qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.IS_ISOLATED)} as is_isolated,
            vca.{cluster_assignments_cluster_id} as spatial_cluster_id,
            sc.{spatial_clusters_cluster_size} as cluster_size
        FROM {spatial_features_table} vsf
        LEFT JOIN {cluster_assignments_table} vca
            ON vsf.{spatial_features_village_id} = vca.{cluster_assignments_village_id} AND vca.{cluster_assignments_run_id} = ?
        LEFT JOIN {spatial_clusters_table} sc
            ON vca.{cluster_assignments_run_id} = sc.{spatial_clusters_run_id} AND vca.{cluster_assignments_cluster_id} = sc.{spatial_clusters_cluster_id}
        WHERE vsf.{spatial_features_village_id} = ?
    """

    result = execute_single(db, query, (clustering_version, village_info['village_id']))

    if not result:
        # Return empty dict if no spatial feature data exists
        return {
            "message": "No spatial feature data available for this village",
            "village_id": f'v_{village_id}'
        }

    return result


@router.get("/complete/{village_id}")
def get_village_complete_profile(
    village_id: int,
    db: sqlite3.Connection = Depends(get_db),
    dbpath: str = Depends(get_dbpath),
):
    """
    获取村庄的完整档案（所有数据）
    Get complete profile for a village (all available data)

    Args:
        village_id: 村庄ID (ROWID from main table)

    Returns:
        dict: 村庄完整档案
    """
    villages_table = qtable(dbpath, T.VILLAGES)
    villages_rowid = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.ROWID)
    villages_id = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.VILLAGE_ID)
    villages_name = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.NAME)
    villages_city = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.CITY)
    villages_county = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COUNTY)
    villages_township = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.TOWNSHIP)
    villages_committee = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.COMMITTEE)
    villages_longitude = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.LONGITUDE)
    villages_latitude = qcolumn(dbpath, T.VILLAGES, C.VILLAGES.LATITUDE)
    features_table = qtable(dbpath, T.VILLAGE_FEATURES)
    features_village_id = qcolumn(dbpath, T.VILLAGE_FEATURES, C.VILLAGE_FEATURES.VILLAGE_ID)
    spatial_features_table = qtable(dbpath, T.VILLAGE_SPATIAL_FEATURES)
    spatial_features_village_id = qcolumn(dbpath, T.VILLAGE_SPATIAL_FEATURES, C.VILLAGE_SPATIAL_FEATURES.VILLAGE_ID)
    cluster_assignments_table = qtable(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS)
    cluster_assignments_village_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.VILLAGE_ID)
    cluster_assignments_run_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.RUN_ID)
    cluster_assignments_cluster_id = qcolumn(dbpath, T.VILLAGE_CLUSTER_ASSIGNMENTS, C.VILLAGE_CLUSTER_ASSIGNMENTS.CLUSTER_ID)
    spatial_clusters_table = qtable(dbpath, T.SPATIAL_CLUSTERS)
    spatial_clusters_run_id = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.RUN_ID)
    spatial_clusters_cluster_id = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CLUSTER_ID)
    spatial_clusters_cluster_size = qcolumn(dbpath, T.SPATIAL_CLUSTERS, C.SPATIAL_CLUSTERS.CLUSTER_SIZE)
    semantic_table = qtable(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE)
    semantic_name = qcolumn(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE, C.VILLAGE_SEMANTIC_STRUCTURE.NAME)
    semantic_committee = qcolumn(dbpath, T.VILLAGE_SEMANTIC_STRUCTURE, C.VILLAGE_SEMANTIC_STRUCTURE.COMMITTEE)
    ngrams_table = qtable(dbpath, T.VILLAGE_NGRAMS)
    ngrams_name = qcolumn(dbpath, T.VILLAGE_NGRAMS, C.VILLAGE_NGRAMS.NAME)
    ngrams_committee = qcolumn(dbpath, T.VILLAGE_NGRAMS, C.VILLAGE_NGRAMS.COMMITTEE)

    # Get basic info from preprocessed table using ROWID
    basic_query = f"""
        SELECT
            {villages_rowid} as village_id,
            {villages_name} as village_name,
            {villages_city} as city,
            {villages_county} as county,
            {villages_township} as township,
            {villages_committee} as village_committee,
            CAST({villages_longitude} AS REAL) as longitude,
            CAST({villages_latitude} AS REAL) as latitude,
            {villages_id} as village_id_str
        FROM {villages_table}
        WHERE {villages_rowid} = ?
    """
    basic_info = execute_single(db, basic_query, (village_id,))

    if not basic_info:
        raise HTTPException(
            status_code=404,
            detail=f"Village {village_id} not found"
        )

    # Get village features (no run_id needed)
    features_query = f"""
        SELECT *
        FROM {features_table}
        WHERE {features_village_id} = ?
    """
    features = execute_single(db, features_query, (basic_info['village_id_str'],))

    # Get spatial features (with clustering info from new table)
    spatial_cluster_run_id = get_run_id_manager(dbpath).get_active_run_id(
        run_id_analysis_type(dbpath, T.SPATIAL_CLUSTERS)
    )
    spatial_query = f"""
        SELECT
            vsf.*,
            vca.{cluster_assignments_cluster_id} as spatial_cluster_id,
            sc.{spatial_clusters_cluster_size} as cluster_size
        FROM {spatial_features_table} vsf
        LEFT JOIN {cluster_assignments_table} vca
            ON vsf.{spatial_features_village_id} = vca.{cluster_assignments_village_id} AND vca.{cluster_assignments_run_id} = ?
        LEFT JOIN {spatial_clusters_table} sc
            ON vca.{cluster_assignments_run_id} = sc.{spatial_clusters_run_id} AND vca.{cluster_assignments_cluster_id} = sc.{spatial_clusters_cluster_id}
        WHERE vsf.{spatial_features_village_id} = ?
    """
    spatial_features = execute_single(db, spatial_query, (spatial_cluster_run_id, basic_info['village_id_str']))

    # Get semantic structure (uses village_name + committee)
    semantic_query = f"""
        SELECT *
        FROM {semantic_table}
        WHERE {semantic_name} = ? AND {semantic_committee} = ?
    """
    semantic_structure = execute_single(db, semantic_query, (
        basic_info['village_name'],
        basic_info['village_committee']
    ))

    # Fallback: try matching by village_name only
    if not semantic_structure:
        semantic_query = f"""
            SELECT *
            FROM {semantic_table}
            WHERE {semantic_name} = ?
        """
        semantic_structure = execute_single(db, semantic_query, (basic_info['village_name'],))

    # Get n-grams (uses village_name + committee)
    ngrams_query = f"""
        SELECT *
        FROM {ngrams_table}
        WHERE {ngrams_name} = ? AND {ngrams_committee} = ?
    """
    ngrams = execute_single(db, ngrams_query, (
        basic_info['village_name'],
        basic_info['village_committee']
    ))

    # Fallback: try matching by village_name only
    if not ngrams:
        ngrams_query = f"""
            SELECT *
            FROM {ngrams_table}
            WHERE {ngrams_name} = ?
        """
        ngrams = execute_single(db, ngrams_query, (basic_info['village_name'],))

    # Get features (uses village_id)
    features_query = f"""
        SELECT *
        FROM {features_table}
        WHERE {features_village_id} = ?
    """
    features = execute_single(db, features_query, (basic_info['village_id_str'],))

    return {
        "basic_info": basic_info,
        "spatial_features": spatial_features,
        "semantic_structure": semantic_structure,
        "ngrams": ngrams,
        "features": features
    }
