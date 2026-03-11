"""
在线计算模块 (Online Computation Module)

提供参数化的实时分析接口，包括：
- 聚类分析 (Clustering)
- 语义分析 (Semantic Analysis)
- 特征提取 (Feature Extraction)
- 子集分析 (Subset Analysis)

性能约束：
- 响应时间 <3秒
- 内存占用 <500MB
- 支持缓存和超时控制
"""

from .cache import compute_cache
from .engine import ClusteringEngine, SemanticEngine, FeatureEngine

__all__ = [
    'compute_cache',
    'ClusteringEngine',
    'SemanticEngine',
    'FeatureEngine'
]
