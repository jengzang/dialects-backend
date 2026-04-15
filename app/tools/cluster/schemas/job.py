"""
cluster 请求体与任务状态相关 schema。

这一层定义的是前后端之间的接口契约，重点包括：
- 一个 group 如何描述“拿哪些字、比哪个维度”；
- clustering 如何描述“用哪个聚类器、哪个音系模式”；
- 任务创建、轮询时前端能拿到哪些摘要字段。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


class ClusterSourceMode(str, Enum):
    """group 字集来源：预设字表查询或直接自定义字串。"""
    PRESET = "preset"
    CUSTOM = "custom"


class ClusterCompareDimension(str, Enum):
    """当前 group 比较的是声母、韵母还是声调。"""
    INITIAL = "initial"
    FINAL = "final"
    TONE = "tone"


class ClusterAlgorithm(str, Enum):
    """当前支持的四种聚类器。"""
    AGGLOMERATIVE = "agglomerative"
    DBSCAN = "dbscan"
    KMEANS = "kmeans"
    GMM = "gmm"


class ClusterMetricMode(str, Enum):
    """旧字段，保留兼容；当前计算主线已经改为 phoneme_mode。"""
    CORRESPONDENCE = "correspondence"
    SYSTEM_PROFILE = "system_profile"
    HOMOPHONY_EMBEDDING = "homophony_embedding"
    HYBRID_PHONOLOGY = "hybrid_phonology"


class ClusterPhonemeMode(str, Enum):
    """三种音系距离模式。"""
    INTRA_GROUP = "intra_group"
    ANCHORED_INVENTORY = "anchored_inventory"
    SHARED_REQUEST_IDENTITY = "shared_request_identity"


class AgglomerativeLinkage(str, Enum):
    """层次聚类允许的 linkage 类型。"""
    AVERAGE = "average"
    COMPLETE = "complete"
    SINGLE = "single"


class ClusterGroupRequest(BaseModel):
    """
    单个 group 的请求结构。

    可以把一个 group 理解为：
    “从某个来源解析出一组汉字，然后在某个音系维度上比较所有地点。”

    例如 16 摄聚韵母时，通常就是 16 个 group，每个 group 对应一个摄。
    """
    label: Optional[str] = Field(default=None, max_length=100)
    source_mode: ClusterSourceMode

    table_name: str = Field(default="characters")
    path_strings: Optional[List[str]] = Field(
        default=None,
        description="Optional charlist-compatible query payload.",
    )
    column: Optional[List[str]] = None
    combine_query: bool = False
    filters: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Structured preset filters: OR within field, AND across fields.",
    )
    exclude_columns: Optional[List[str]] = None

    custom_chars: Optional[Union[str, List[str]]] = None
    resolved_chars: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Optional already-resolved character list shortcut.",
    )

    compare_dimension: ClusterCompareDimension
    group_weight: float = Field(default=1.0, gt=0)
    use_phonetic_values: bool = False
    phonetic_value_weight: float = Field(default=0.2, ge=0.0, le=1.0)

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, value: str) -> str:
        """限制字表只能来自系统允许的 characters 类表。"""
        from app.common.constants import VALID_CHARACTER_TABLES

        if value not in VALID_CHARACTER_TABLES:
            raise ValueError(
                f"Invalid table_name: {value}. Must be one of {VALID_CHARACTER_TABLES}"
            )
        return value

    @field_validator("path_strings")
    @classmethod
    def validate_path_strings(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        """清洗 charlist 风格路径输入。"""
        if value is None:
            return value
        cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return cleaned or None

    @field_validator("column", "exclude_columns")
    @classmethod
    def validate_optional_str_list(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        """清洗可选字符串数组字段，去掉空值和纯空白。"""
        if value is None:
            return value
        cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return cleaned or None

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, value: Optional[Dict[str, List[str]]]) -> Optional[Dict[str, List[str]]]:
        """清洗旧版 structured filters 输入。"""
        if value is None:
            return value

        cleaned: Dict[str, List[str]] = {}
        for key, raw_values in value.items():
            if not isinstance(key, str) or not key.strip():
                continue
            values = [
                item.strip()
                for item in (raw_values or [])
                if isinstance(item, str) and item.strip()
            ]
            if values:
                cleaned[key.strip()] = values
        return cleaned or None

    @model_validator(mode="after")
    def validate_source_payload(self):
        """不同 source_mode 必须至少提供一种可解析的字集来源。"""
        if self.source_mode == ClusterSourceMode.CUSTOM:
            if not self.custom_chars and not self.resolved_chars:
                raise ValueError("custom source_mode requires custom_chars or resolved_chars")
        else:
            if not self.path_strings and not self.filters and not self.resolved_chars:
                raise ValueError(
                    "preset source_mode requires path_strings, filters, or resolved_chars"
                )
        return self


class ClusterAlgorithmConfigRequest(BaseModel):
    """纯聚类器配置；staged API 的最后一步只需要这部分参数。"""
    algorithm: ClusterAlgorithm
    n_clusters: Optional[int] = Field(default=None, ge=2, le=100)
    linkage: AgglomerativeLinkage = AgglomerativeLinkage.AVERAGE
    eps: float = Field(default=0.5, gt=0.0, le=10.0)
    min_samples: int = Field(default=5, ge=1, le=100)
    random_state: int = Field(default=42, ge=0)

    @model_validator(mode="after")
    def validate_algorithm_params(self):
        """对不同聚类器做交叉字段校验。"""
        if self.algorithm in {ClusterAlgorithm.AGGLOMERATIVE, ClusterAlgorithm.KMEANS, ClusterAlgorithm.GMM}:
            if self.n_clusters is None:
                raise ValueError("n_clusters is required for agglomerative/kmeans/gmm")
        elif self.algorithm == ClusterAlgorithm.DBSCAN and self.n_clusters is not None:
            raise ValueError("n_clusters should not be specified for dbscan")
        return self


class ClusterConfigRequest(ClusterAlgorithmConfigRequest):
    """旧 one-shot API 使用的完整配置，包含 phoneme_mode。"""
    phoneme_mode: ClusterPhonemeMode = ClusterPhonemeMode.INTRA_GROUP
    metric_mode: Optional[ClusterMetricMode] = Field(
        default=None,
        description="Deprecated legacy field. Use phoneme_mode instead.",
    )


class ClusterRequestBase(BaseModel):
    """
    cluster 输入请求的公共部分。

    它由三部分组成：
    - `groups`：定义比较哪些字、比较哪个维度；
    - `locations/regions`：定义要聚哪些地点；
    - `clustering`：仅旧 one-shot API 需要，staged API 会延后到最后一步。
    """
    groups: List[ClusterGroupRequest] = Field(..., min_length=1)
    locations: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("locations", "location"),
    )
    regions: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("regions", "region"),
    )
    region_mode: str = Field(
        default="yindian",
        validation_alias=AliasChoices("region_mode", "regiontype", "regionType"),
        description="yindian or map",
    )
    include_special_locations: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "include_special_locations",
            "includeSpecialLocations",
        ),
        description="是否保留域外方音/歷史音/標準語/民語漢字音等特殊點；默認 false 會過濾",
    )
    @field_validator("locations", "regions", mode="before")
    @classmethod
    def normalize_locations_regions_input(cls, value):
        """兼容字符串、列表、集合等多种输入形态。"""
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return [str(value)]

    @field_validator("locations", "regions")
    @classmethod
    def validate_locations_regions(cls, value: List[str]) -> List[str]:
        """去掉空白地点名与空字符串。"""
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    @field_validator("region_mode")
    @classmethod
    def validate_region_mode(cls, value: str) -> str:
        """限制分区模式只能使用音典分区或地图集分区。"""
        if value not in {"yindian", "map"}:
            raise ValueError("region_mode must be 'yindian' or 'map'")
        return value

    @model_validator(mode="after")
    def validate_locations_or_regions(self):
        """地点与分区至少提供一种，否则无法展开候选地点。"""
        if not self.locations and not self.regions:
            raise ValueError("locations 和 regions 不能同時為空，至少提供其一")
        return self


class ClusterJobCreateRequest(ClusterRequestBase):
    """旧 one-shot cluster API 的请求结构。"""
    clustering: ClusterConfigRequest


class ClusterStageSessionCreateRequest(ClusterRequestBase):
    """staged cluster session 创建请求；只冻结输入，不立即指定算法。"""


class ClusterStageDistanceRequest(BaseModel):
    """staged API 的 distance 阶段请求。"""
    phoneme_mode: ClusterPhonemeMode


class ClusterStageClusterRequest(BaseModel):
    """staged API 的 cluster 阶段请求。"""
    distance_id: str = Field(..., min_length=1, max_length=128)
    clustering: ClusterAlgorithmConfigRequest


class ClusterJobStatusResponse(BaseModel):
    """任务轮询响应，包含进度、耗时与性能分段信息。"""
    task_id: str
    status: str
    progress: float
    message: str
    created_at: float
    updated_at: float
    summary: Optional[dict] = None
    execution_time_ms: Optional[int] = None
    performance: Optional[dict] = None
