# 批量向量比较、降维、聚类 API 的 Pydantic 模型和端点

from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# ============================================================================
# Batch Vector Comparison API
# ============================================================================

class RegionSpec(BaseModel):
    """区域规格（层级路径参数）"""
    level: str  # "city" | "county" | "township"
    city: Optional[str] = None
    county: Optional[str] = None
    township: Optional[str] = None


class BatchCompareRequest(BaseModel):
    """批量向量比较请求模型"""
    regions: List[RegionSpec]
    run_id: Optional[str] = None


class BatchCompareResponse(BaseModel):
    """批量向量比较响应模型"""
    regions: List[Dict[str, Any]]  # 区域信息列表
    similarity_matrix: List[List[float]]  # 相似度矩阵（余弦相似度）
    distance_matrix: List[List[float]]  # 距离矩阵（欧氏距离）
    feature_dimension: int
    categories: List[str]
    run_id: str


# ============================================================================
# Vector Dimensionality Reduction API
# ============================================================================

class ReduceRequest(BaseModel):
    """向量降维请求模型"""
    regions: List[RegionSpec]
    method: str = "pca"  # "pca" | "tsne"
    n_components: int = 2  # 2 or 3
    run_id: Optional[str] = None


class ReduceResponse(BaseModel):
    """向量降维响应模型"""
    regions: List[Dict[str, Any]]  # 区域信息列表
    coordinates: List[List[float]]  # 降维后的坐标
    method: str
    n_components: int
    explained_variance: Optional[List[float]] = None  # PCA 专用
    run_id: str


# ============================================================================
# Vector Clustering API
# ============================================================================

class ClusterRequest(BaseModel):
    """向量聚类请求模型"""
    regions: List[RegionSpec]
    method: str = "kmeans"  # "kmeans" | "dbscan" | "gmm"
    n_clusters: Optional[int] = None  # kmeans/gmm 需要
    eps: Optional[float] = None  # dbscan 需要
    min_samples: Optional[int] = None  # dbscan 需要
    run_id: Optional[str] = None


class ClusterResponse(BaseModel):
    """向量聚类响应模型"""
    regions: List[Dict[str, Any]]  # 区域信息列表
    labels: List[int]  # 聚类标签
    n_clusters: int  # 实际聚类数量
    cluster_centers: Optional[List[List[float]]] = None  # kmeans/gmm 专用
    method: str
    run_id: str
