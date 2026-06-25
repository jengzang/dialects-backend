from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FeatureRecord:
    id: int
    pid: int
    deep: int
    name: str
    ext_path: str
    center_lng: float | None
    center_lat: float | None
    source_crs: str
    target_crs: str
    source_file: str
    geometry_type: str | None
    geometry_exists: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pid": self.pid,
            "deep": self.deep,
            "name": self.name,
            "ext_path": self.ext_path,
            "center_lng": self.center_lng,
            "center_lat": self.center_lat,
            "source_crs": self.source_crs,
            "target_crs": self.target_crs,
            "source_file": self.source_file,
            "geometry_type": self.geometry_type,
            "geometry_exists": self.geometry_exists,
        }


@dataclass(slots=True)
class SubGeometryIndexRecord:
    sub_id: int
    feature_id: int
    deep: int
    part_index: int
    part_kind: str
    source_geometry_type: str
    bbox: tuple[float, float, float, float]
    geom_offset: int
    geom_length: int
    subgrid_refs: list[str]


@dataclass(slots=True)
class QueryStats:
    query_count: int = 0
    envelope_hit_count: int = 0
    exact_hit_count: int = 0
    nearest_hit_count: int = 0
    io_reads: int = 0
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    cache_eviction_count: int = 0


@dataclass(slots=True)
class QueryResult:
    result: list[dict[str, Any]] = field(default_factory=list)
    stats: QueryStats = field(default_factory=QueryStats)


@dataclass(slots=True)
class EngineStatus:
    loaded: bool
    mode: str
    feature_count: int
    subgeometry_count: int
    features_with_multiple_parts: int
    split_mode: str
    source_crs: str
    target_crs: str
    storage_format: str
    grid_factor: int
    subgrid_factor: int
    cache_max_items: int
    cache_current_items: int
    cache_hit_count: int
    cache_miss_count: int
    cache_eviction_count: int
    index_path: str
    features_path: str
    geometry_path: str
