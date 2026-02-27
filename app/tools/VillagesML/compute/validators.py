"""
参数验证模块 (Parameter Validation)

使用Pydantic进行请求参数验证
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from enum import Enum


class AlgorithmType(str, Enum):
    """聚类算法类型"""
    KMEANS = "kmeans"
    DBSCAN = "dbscan"
    GMM = "gmm"


class RegionLevel(str, Enum):
    """区域级别"""
    CITY = "city"
    COUNTY = "county"
    TOWNSHIP = "township"


class FeatureConfig(BaseModel):
    """特征配置"""
    use_semantic: bool = True
    use_morphology: bool = True
    use_diversity: bool = True
    top_n_suffix2: int = Field(100, ge=10, le=500)
    top_n_suffix3: int = Field(100, ge=10, le=500)


class PreprocessingConfig(BaseModel):
    """预处理配置"""
    use_pca: bool = True
    pca_n_components: int = Field(50, ge=10, le=200)
    standardize: bool = True


class DBSCANConfig(BaseModel):
    """DBSCAN算法配置"""
    eps: float = Field(0.5, gt=0, le=10, description="邻域半径")
    min_samples: int = Field(5, ge=1, le=20, description="最小样本数")


class ClusteringParams(BaseModel):
    """聚类参数验证"""
    algorithm: AlgorithmType
    k: Optional[int] = Field(None, ge=2, le=20)
    region_level: RegionLevel
    region_filter: Optional[List[str]] = None
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    dbscan_config: Optional[DBSCANConfig] = None
    random_state: int = Field(42, ge=0)

    @validator('k')
    def validate_k(cls, v, values):
        """验证k值"""
        algorithm = values.get('algorithm')
        if algorithm in [AlgorithmType.KMEANS, AlgorithmType.GMM] and v is None:
            raise ValueError("k is required for kmeans/gmm")
        if algorithm == AlgorithmType.DBSCAN and v is not None:
            raise ValueError("k should not be specified for dbscan")
        return v

    @validator('region_filter')
    def validate_region_filter(cls, v):
        """验证区域过滤器"""
        if v and len(v) > 50:
            raise ValueError("region_filter cannot exceed 50 regions")
        return v


class ClusteringScanParams(BaseModel):
    """聚类参数扫描"""
    algorithm: AlgorithmType
    k_range: List[int] = Field(..., min_items=2, max_items=10)
    region_level: RegionLevel
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    metric: str = Field("silhouette_score",
                       pattern="^(silhouette_score|davies_bouldin_index|calinski_harabasz_score)$")

    @validator('k_range')
    def validate_k_range(cls, v):
        """验证k值范围"""
        if not all(2 <= k <= 20 for k in v):
            raise ValueError("All k values must be between 2 and 20")
        if len(set(v)) != len(v):
            raise ValueError("k_range must contain unique values")
        return sorted(v)


class SemanticAnalysisParams(BaseModel):
    """语义分析参数验证"""
    region_level: RegionLevel
    region_name: Optional[str] = None
    min_support: int = Field(10, ge=1, le=1000)
    min_cooccurrence: int = Field(5, ge=1, le=100)
    alpha: float = Field(0.05, gt=0, lt=1)
    categories: Optional[List[str]] = None
    detail: bool = Field(False, description="是否使用详细表（76子类别）")

    @validator('categories')
    def validate_categories(cls, v):
        """验证语义类别"""
        valid_categories = ["水系", "山地", "地形", "方位", "植被", "聚落", "人文", "数量", "其他"]
        if v:
            invalid = set(v) - set(valid_categories)
            if invalid:
                raise ValueError(f"Invalid categories: {invalid}")
        return v


class SemanticNetworkParams(BaseModel):
    """语义网络参数"""
    region_level: RegionLevel
    region_name: Optional[str] = None
    min_edge_weight: float = Field(0.5, ge=0, le=10)
    centrality_metrics: List[str] = Field(["degree", "betweenness"])
    detail: bool = Field(False, description="是否使用详细表（76子类别）")

    @validator('centrality_metrics')
    def validate_centrality_metrics(cls, v):
        """验证中心性指标"""
        valid_metrics = ["degree", "betweenness", "closeness", "eigenvector"]
        invalid = set(v) - set(valid_metrics)
        if invalid:
            raise ValueError(f"Invalid centrality metrics: {invalid}")
        return v


class VillageInput(BaseModel):
    """村庄输入"""
    name: str = Field(..., min_length=1, max_length=50)
    city: Optional[str] = None
    county: Optional[str] = None


class FeatureExtractionParams(BaseModel):
    """特征提取参数"""
    villages: List[VillageInput] = Field(..., min_items=1, max_items=1000)
    features: Dict[str, Any] = Field(default_factory=dict)

    @validator('villages')
    def validate_villages(cls, v):
        """验证村庄列表"""
        if len(v) > 1000:
            raise ValueError("Cannot extract features for more than 1000 villages at once")
        return v


class FeatureAggregationParams(BaseModel):
    """特征聚合参数"""
    region_level: RegionLevel
    region_names: List[str] = Field(..., min_items=1, max_items=50)
    features: Dict[str, Any] = Field(default_factory=dict)
    top_n: int = Field(100, ge=10, le=500)


class SubsetFilter(BaseModel):
    """子集过滤器"""
    cities: Optional[List[str]] = None
    counties: Optional[List[str]] = None
    semantic_tags: Optional[List[str]] = None
    name_pattern: Optional[str] = None
    sample_size: Optional[int] = Field(None, ge=100, le=10000)


class SubsetClusteringParams(BaseModel):
    """子集聚类参数"""
    filter: SubsetFilter
    clustering: Dict[str, Any]


class ComparisonGroup(BaseModel):
    """对比组"""
    filter: SubsetFilter
    label: str = Field(..., min_length=1, max_length=50)


class SubsetComparisonParams(BaseModel):
    """子集对比参数"""
    group_a: ComparisonGroup
    group_b: ComparisonGroup
    analysis: Dict[str, Any] = Field(default_factory=dict)


class TendencyMetric(str, Enum):
    """倾向性指标类型"""
    Z_SCORE = "z_score"
    LIFT = "lift"
    LOG_ODDS = "log_odds"


class SamplingStrategy(str, Enum):
    """采样策略"""
    RANDOM = "random"
    STRATIFIED = "stratified"
    SPATIAL = "spatial"


class CharacterTendencyClusteringParams(BaseModel):
    """字符倾向性聚类参数"""
    algorithm: AlgorithmType
    k: Optional[int] = Field(None, ge=2, le=20)
    region_level: RegionLevel
    region_filter: Optional[List[str]] = None
    top_n_chars: int = Field(100, ge=10, le=500, description="每个区域选择top N字符")
    tendency_metric: TendencyMetric = TendencyMetric.Z_SCORE
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    random_state: int = Field(42, ge=0)

    @validator('k')
    def validate_k(cls, v, values):
        """验证k值"""
        algorithm = values.get('algorithm')
        if algorithm in [AlgorithmType.KMEANS, AlgorithmType.GMM] and v is None:
            raise ValueError("k is required for kmeans/gmm")
        if algorithm == AlgorithmType.DBSCAN and v is not None:
            raise ValueError("k should not be specified for dbscan")
        return v


class SampledVillageClusteringParams(BaseModel):
    """采样村庄聚类参数"""
    algorithm: AlgorithmType
    k: Optional[int] = Field(None, ge=2, le=20)
    sampling_strategy: SamplingStrategy = SamplingStrategy.RANDOM
    sample_size: int = Field(5000, ge=100, le=10000, description="采样大小")
    filter: Optional[SubsetFilter] = None
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    random_state: int = Field(42, ge=0)

    @validator('k')
    def validate_k(cls, v, values):
        """验证k值"""
        algorithm = values.get('algorithm')
        if algorithm in [AlgorithmType.KMEANS, AlgorithmType.GMM] and v is None:
            raise ValueError("k is required for kmeans/gmm")
        if algorithm == AlgorithmType.DBSCAN and v is not None:
            raise ValueError("k should not be specified for dbscan")
        return v


class SpatialAwareClusteringParams(BaseModel):
    """空间感知聚类参数"""
    algorithm: AlgorithmType
    k: Optional[int] = Field(None, ge=2, le=20)
    spatial_run_id: str = Field(..., description="空间聚类运行ID")
    features: Dict[str, bool] = Field(
        default_factory=lambda: {
            "use_semantic_profile": True,
            "use_naming_patterns": True,
            "use_geographic": True,
            "use_cluster_size": True
        }
    )
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    random_state: int = Field(42, ge=0)

    @validator('k')
    def validate_k(cls, v, values):
        """验证k值"""
        algorithm = values.get('algorithm')
        if algorithm in [AlgorithmType.KMEANS, AlgorithmType.GMM] and v is None:
            raise ValueError("k is required for kmeans/gmm")
        if algorithm == AlgorithmType.DBSCAN and v is not None:
            raise ValueError("k should not be specified for dbscan")
        return v


class HierarchicalClusteringParams(BaseModel):
    """层次聚类参数"""
    algorithm: AlgorithmType
    k_city: int = Field(3, ge=2, le=10, description="市级聚类数")
    k_county: int = Field(8, ge=2, le=15, description="县级聚类数")
    k_township: int = Field(15, ge=2, le=30, description="镇级聚类数")
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    random_state: int = Field(42, ge=0)

    @validator('algorithm')
    def validate_algorithm(cls, v):
        """验证算法类型"""
        if v == AlgorithmType.DBSCAN:
            raise ValueError("DBSCAN is not supported for hierarchical clustering")
        return v
