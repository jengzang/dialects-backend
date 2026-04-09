"""
Cluster request and task-status schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


class ClusterSourceMode(str, Enum):
    PRESET = "preset"
    CUSTOM = "custom"


class ClusterCompareDimension(str, Enum):
    INITIAL = "initial"
    FINAL = "final"
    TONE = "tone"


class ClusterAlgorithm(str, Enum):
    AGGLOMERATIVE = "agglomerative"
    DBSCAN = "dbscan"
    KMEANS = "kmeans"
    GMM = "gmm"


class ClusterMetricMode(str, Enum):
    CORRESPONDENCE = "correspondence"
    SYSTEM_PROFILE = "system_profile"
    HOMOPHONY_EMBEDDING = "homophony_embedding"
    HYBRID_PHONOLOGY = "hybrid_phonology"


class ClusterPhonemeMode(str, Enum):
    INTRA_GROUP = "intra_group"
    ANCHORED_INVENTORY = "anchored_inventory"
    SHARED_REQUEST_IDENTITY = "shared_request_identity"


class AgglomerativeLinkage(str, Enum):
    AVERAGE = "average"
    COMPLETE = "complete"
    SINGLE = "single"


class ClusterGroupRequest(BaseModel):
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
        from app.common.constants import VALID_CHARACTER_TABLES

        if value not in VALID_CHARACTER_TABLES:
            raise ValueError(
                f"Invalid table_name: {value}. Must be one of {VALID_CHARACTER_TABLES}"
            )
        return value

    @field_validator("path_strings")
    @classmethod
    def validate_path_strings(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return cleaned or None

    @field_validator("column", "exclude_columns")
    @classmethod
    def validate_optional_str_list(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return cleaned or None

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, value: Optional[Dict[str, List[str]]]) -> Optional[Dict[str, List[str]]]:
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
        if self.source_mode == ClusterSourceMode.CUSTOM:
            if not self.custom_chars and not self.resolved_chars:
                raise ValueError("custom source_mode requires custom_chars or resolved_chars")
        else:
            if not self.path_strings and not self.filters and not self.resolved_chars:
                raise ValueError(
                    "preset source_mode requires path_strings, filters, or resolved_chars"
                )
        return self


class ClusterConfigRequest(BaseModel):
    algorithm: ClusterAlgorithm
    phoneme_mode: ClusterPhonemeMode = ClusterPhonemeMode.INTRA_GROUP
    metric_mode: Optional[ClusterMetricMode] = Field(
        default=None,
        description="Deprecated legacy field. Use phoneme_mode instead.",
    )
    n_clusters: Optional[int] = Field(default=None, ge=2, le=100)
    linkage: AgglomerativeLinkage = AgglomerativeLinkage.AVERAGE
    eps: float = Field(default=0.5, gt=0.0, le=10.0)
    min_samples: int = Field(default=5, ge=1, le=100)
    random_state: int = Field(default=42, ge=0)

    @model_validator(mode="after")
    def validate_algorithm_params(self):
        if self.algorithm in {ClusterAlgorithm.AGGLOMERATIVE, ClusterAlgorithm.KMEANS, ClusterAlgorithm.GMM}:
            if self.n_clusters is None:
                raise ValueError("n_clusters is required for agglomerative/kmeans/gmm")
        elif self.algorithm == ClusterAlgorithm.DBSCAN and self.n_clusters is not None:
            raise ValueError("n_clusters should not be specified for dbscan")
        return self


class ClusterJobCreateRequest(BaseModel):
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
    clustering: ClusterConfigRequest

    @field_validator("locations", "regions", mode="before")
    @classmethod
    def normalize_locations_regions_input(cls, value):
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
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    @field_validator("region_mode")
    @classmethod
    def validate_region_mode(cls, value: str) -> str:
        if value not in {"yindian", "map"}:
            raise ValueError("region_mode must be 'yindian' or 'map'")
        return value

    @model_validator(mode="after")
    def validate_locations_or_regions(self):
        if not self.locations and not self.regions:
            raise ValueError("locations 和 regions 不能同時為空，至少提供其一")
        return self


class ClusterJobStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    message: str
    created_at: float
    updated_at: float
    summary: Optional[dict] = None
