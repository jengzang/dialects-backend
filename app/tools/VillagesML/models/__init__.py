"""
Pydantic响应模型
Pydantic response models for API endpoints
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


# ============================================================================
# 通用模型 (Common Models)
# ============================================================================

class PaginatedResponse(BaseModel):
    """分页响应模型"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    data: List[Any] = Field(..., description="数据列表")


# ============================================================================
# 字符分析模型 (Character Analysis Models)
# ============================================================================

class CharFrequency(BaseModel):
    """字符频率模型"""
    character: str = Field(..., description="字符")
    frequency: float = Field(..., description="出现频次")
    village_count: int = Field(..., description="村庄数量")
    rank: int = Field(..., description="排名")


class RegionalCharFrequency(BaseModel):
    """区域字符频率模型"""
    region_name: str = Field(..., description="区域名称")
    character: str = Field(..., description="字符")
    frequency: float = Field(..., description="频次")
    rank: int = Field(..., description="区域内排名")


class CharTendency(BaseModel):
    """字符倾向性模型"""
    character: str = Field(..., description="字符")
    lift: float = Field(..., description="Lift值")
    log_odds: float = Field(..., description="Log-odds值")
    z_score: float = Field(..., description="Z-score值")
    rank: int = Field(..., description="排名")


class CharTendencyByRegion(BaseModel):
    """按字符查询的区域倾向性"""
    region_name: str = Field(..., description="区域名称")
    lift: float = Field(..., description="Lift值")
    z_score: float = Field(..., description="Z-score值")


class CharSignificance(BaseModel):
    """字符统计显著性模型"""
    character: str = Field(..., description="字符")
    chi_square: float = Field(..., description="卡方值")
    p_value: float = Field(..., description="P值")
    effect_size: float = Field(..., description="效应量")
    is_significant: bool = Field(..., description="是否显著")


# ============================================================================
# 模式分析模型 (Pattern Analysis Models)
# ============================================================================

class NgramFrequency(BaseModel):
    """N-gram频率模型"""
    pattern: str = Field(..., description="N-gram模式")
    frequency: float = Field(..., description="频次")
    village_count: int = Field(..., description="村庄数量")


class NgramTendency(BaseModel):
    """N-gram倾向性模型"""
    pattern: str = Field(..., description="N-gram模式")
    lift: float = Field(..., description="Lift值")
    z_score: float = Field(..., description="Z-score值")


class StructuralPattern(BaseModel):
    """结构模式模型"""
    pattern_id: str = Field(..., description="模式ID")
    template: str = Field(..., description="模式模板")
    frequency: float = Field(..., description="频次")
    examples: List[str] = Field(..., description="示例村名")


# ============================================================================
# 语义分析模型 (Semantic Analysis Models)
# ============================================================================

class SemanticCategory(BaseModel):
    """语义类别模型"""
    category: str = Field(..., description="类别名称")
    description: str = Field(..., description="类别描述")
    character_count: int = Field(..., description="字符数量")


class SemanticVTF(BaseModel):
    """语义虚拟词频模型"""
    category: str = Field(..., description="语义类别")
    vtf: float = Field(..., description="虚拟词频")
    character_count: int = Field(..., description="字符数量")


class RegionalSemanticVTF(BaseModel):
    """区域语义虚拟词频模型"""
    region_name: str = Field(..., description="区域名称")
    category: str = Field(..., description="语义类别")
    vtf: float = Field(..., description="虚拟词频")
    intensity_index: float = Field(..., description="强度指数")


class SemanticTendency(BaseModel):
    """语义倾向性模型"""
    category: str = Field(..., description="语义类别")
    lift: float = Field(..., description="Lift值")
    z_score: float = Field(..., description="Z-score值")


class SemanticCooccurrence(BaseModel):
    """语义共现模型"""
    category1: str = Field(..., description="类别1")
    category2: str = Field(..., description="类别2")
    cooccurrence_count: int = Field(..., description="共现次数")
    pmi: float = Field(..., description="PMI分数")
    significance: float = Field(..., description="显著性")


class NetworkEdge(BaseModel):
    """网络边模型"""
    source: str = Field(..., description="源节点")
    target: str = Field(..., description="目标节点")
    weight: float = Field(..., description="边权重")
    edge_type: str = Field(..., description="边类型")


class NodeCentrality(BaseModel):
    """节点中心性模型"""
    category: str = Field(..., description="语义类别")
    centrality_score: float = Field(..., description="中心性分数")
    rank: int = Field(..., description="排名")


# ============================================================================
# 空间分析模型 (Spatial Analysis Models)
# ============================================================================

class SpatialFeature(BaseModel):
    """空间特征模型"""
    village_name: str = Field(..., description="村名")
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")
    knn_mean_distance: float = Field(..., description="k-NN平均距离")
    local_density: float = Field(..., description="局部密度")
    isolation_score: float = Field(..., description="孤立度")


class SpatialCluster(BaseModel):
    """空间聚类模型"""
    cluster_id: int = Field(..., description="聚类ID")
    village_count: int = Field(..., description="村庄数量")
    centroid_lon: float = Field(..., description="中心经度")
    centroid_lat: float = Field(..., description="中心纬度")
    avg_density: float = Field(..., description="平均密度")


class VillageInCluster(BaseModel):
    """聚类中的村庄"""
    village_name: str = Field(..., description="村名")
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")


class Hotspot(BaseModel):
    """热点区域模型"""
    hotspot_id: int = Field(..., description="热点ID")
    center_lon: float = Field(..., description="中心经度")
    center_lat: float = Field(..., description="中心纬度")
    intensity: float = Field(..., description="强度")
    village_count: int = Field(..., description="村庄数量")


# ============================================================================
# 聚类分析模型 (Clustering Analysis Models)
# ============================================================================

class ClusterAssignment(BaseModel):
    """聚类分配模型"""
    region_name: str = Field(..., description="区域名称")
    cluster_id: int = Field(..., description="聚类ID")
    distance_to_centroid: Optional[float] = Field(None, description="到中心距离")


class ClusterProfile(BaseModel):
    """聚类画像模型"""
    cluster_id: int = Field(..., description="聚类ID")
    region_count: int = Field(..., description="区域数量")
    top_semantic_features: Dict[str, float] = Field(..., description="语义特征")
    top_morphology_features: Dict[str, float] = Field(..., description="形态特征")
    distinguishing_features: List[str] = Field(..., description="区分性特征")


class ClusteringMetrics(BaseModel):
    """聚类指标模型"""
    algorithm: str = Field(..., description="算法名称")
    k: int = Field(..., description="聚类数")
    silhouette_score: float = Field(..., description="轮廓系数")
    davies_bouldin_index: float = Field(..., description="DB指数")
    calinski_harabasz_score: float = Field(..., description="CH分数")


# ============================================================================
# 村庄查询模型 (Village Query Models)
# ============================================================================

class VillageBasic(BaseModel):
    """村庄基础信息模型"""
    village_id: int = Field(..., description="村庄ID")
    village_name: str = Field(..., description="村名")
    city: str = Field(..., description="城市")
    county: str = Field(..., description="区县")
    township: str = Field(..., description="乡镇")
    longitude: Optional[float] = Field(None, description="经度")
    latitude: Optional[float] = Field(None, description="纬度")


class VillageDetail(BaseModel):
    """村庄详情模型"""
    basic_info: VillageBasic = Field(..., description="基础信息")
    semantic_tags: List[str] = Field(..., description="语义标签")
    suffix: str = Field(..., description="后缀")
    cluster_id: Optional[int] = Field(None, description="聚类ID")
    spatial_features: Optional[Dict] = Field(None, description="空间特征")


# ============================================================================
# 区域聚合模型 (Regional Aggregation Models)
# ============================================================================

class CityStats(BaseModel):
    """城市统计模型"""
    city: str = Field(..., description="城市名称")
    village_count: int = Field(..., description="村庄数量")
    unique_chars: int = Field(..., description="唯一字符数")
    avg_name_length: float = Field(..., description="平均名称长度")
    top_semantic_categories: Dict[str, float] = Field(..., description="语义类别")
    top_suffixes: List[str] = Field(..., description="高频后缀")


class CountyStats(BaseModel):
    """区县统计模型"""
    county: str = Field(..., description="区县名称")
    city: str = Field(..., description="所属城市")
    village_count: int = Field(..., description="村庄数量")
    cluster_id: Optional[int] = Field(None, description="聚类ID")
    semantic_profile: Dict[str, float] = Field(..., description="语义画像")


class TownshipStats(BaseModel):
    """乡镇统计模型"""
    township: str = Field(..., description="乡镇名称")
    county: str = Field(..., description="所属区县")
    village_count: int = Field(..., description="村庄数量")


# ============================================================================
# 元数据模型 (Metadata Models)
# ============================================================================

class AnalysisRun(BaseModel):
    """分析运行模型"""
    run_id: str = Field(..., description="运行ID")
    run_type: str = Field(..., description="运行类型")
    created_at: datetime = Field(..., description="创建时间")
    total_villages: int = Field(..., description="村庄总数")
    status: str = Field(..., description="状态")
    config: Dict = Field(..., description="配置信息")


class AnalysisRunDetail(AnalysisRun):
    """分析运行详情模型"""
    tables_created: List[str] = Field(..., description="创建的表")
    execution_time: Optional[float] = Field(None, description="执行时间(秒)")


class SystemOverview(BaseModel):
    """系统概览模型"""
    total_villages: int = Field(..., description="村庄总数")
    total_cities: int = Field(..., description="城市总数")
    total_counties: int = Field(..., description="区县总数")
    total_townships: int = Field(..., description="乡镇总数")
    unique_characters: int = Field(..., description="唯一字符数")
    database_size_mb: float = Field(..., description="数据库大小(MB)")
    last_updated: datetime = Field(..., description="最后更新时间")


class TableInfo(BaseModel):
    """表信息模型"""
    table_name: str = Field(..., description="表名")
    row_count: int = Field(..., description="行数")
    size_mb: float = Field(..., description="大小(MB)")
