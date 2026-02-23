"""
Pydantic响应模型 (Response Models)

定义API响应的数据模型
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ClusteringResult(BaseModel):
    """聚类结果模型"""
    run_id: str
    algorithm: str
    k: Optional[int]
    n_regions: int
    execution_time_ms: int
    metrics: Dict[str, float]
    assignments: List[Dict[str, Any]]
    cluster_profiles: List[Dict[str, Any]]
    from_cache: bool = False


class ClusteringScanResult(BaseModel):
    """聚类扫描结果模型"""
    scan_id: str
    results: List[Dict[str, Any]]
    best_k: int
    best_score: float
    total_time_ms: int
    from_cache: bool = False


class CooccurrenceResult(BaseModel):
    """共现分析结果模型"""
    analysis_id: str
    region_name: str
    execution_time_ms: int
    cooccurrence_matrix: List[Dict[str, Any]]
    significant_pairs: List[Dict[str, Any]]
    from_cache: bool = False


class SemanticNetworkResult(BaseModel):
    """语义网络结果模型"""
    network_id: str
    node_count: int
    edge_count: int
    execution_time_ms: int
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    communities: List[Dict[str, Any]]
    from_cache: bool = False


class FeatureExtractionResult(BaseModel):
    """特征提取结果模型"""
    extraction_id: str
    village_count: int
    execution_time_ms: int
    features: List[Dict[str, Any]]
    from_cache: bool = False


class FeatureAggregationResult(BaseModel):
    """特征聚合结果模型"""
    aggregation_id: str
    region_count: int
    execution_time_ms: int
    regional_features: List[Dict[str, Any]]
    from_cache: bool = False


class SubsetClusteringResult(BaseModel):
    """子集聚类结果模型"""
    subset_id: str
    matched_villages: int
    sampled_villages: int
    execution_time_ms: int
    clusters: List[Dict[str, Any]]
    metrics: Dict[str, float]
    from_cache: bool = False


class SubsetComparisonResult(BaseModel):
    """子集对比结果模型"""
    comparison_id: str
    group_a_size: int
    group_b_size: int
    execution_time_ms: int
    semantic_comparison: List[Dict[str, Any]]
    morphology_comparison: List[Dict[str, Any]]
    significant_differences: List[Dict[str, Any]]
    from_cache: bool = False


class CacheStats(BaseModel):
    """缓存统计模型"""
    cache_size: int
    max_size: int
    hit_count: int
    miss_count: int
    hit_rate: float
    ttl_seconds: int


class ErrorResponse(BaseModel):
    """错误响应模型"""
    detail: str
    error_type: Optional[str] = None
    timestamp: Optional[str] = None
