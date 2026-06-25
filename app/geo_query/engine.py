from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Callable

from .cache import LRUCache
from .config import (
    GEO_CACHE_MAX_ITEMS,
    GEO_FEATURES_JSONL_PATH,
    GEO_GRID_FACTOR,
    GEO_INDEX_JSON_PATH,
    GEO_META_JSON_PATH,
    GEO_POINT_TOLERANCE_METRE,
    GEO_SUBGEOM_WKB_PATH,
)
from .geometry_store import GeometryStore
from .index_store import load_features, load_index
from .models import EngineStatus, QueryResult, SubGeometryIndexRecord
from .query_ops import geometry_query, point_query, point_query_with_tolerance

WhereFn = Callable[[dict], bool] | None
_CACHE_SENTINEL = object()


class AreaCityQueryPy:
    def __init__(self):
        self.loaded = False
        self.mode = "lowmem"
        self.features = {}
        self.index_records: list[SubGeometryIndexRecord] = []
        self.record_by_sub_id: dict[int, SubGeometryIndexRecord] = {}
        self.grid_index: dict[str, list[int]] = {}
        self.subgrid_index: dict[str, list[int]] = {}
        self.feature_parts: dict[int, list[int]] = {}
        self.geometry_store: GeometryStore | None = None
        self.meta: dict = {}
        self._geometry_cache = LRUCache[int, object](GEO_CACHE_MAX_ITEMS)
        self._init_lock = Lock()

    def init_store_in_wkb_file(
        self,
        index_path: Path = GEO_INDEX_JSON_PATH,
        features_path: Path = GEO_FEATURES_JSONL_PATH,
        geometry_path: Path = GEO_SUBGEOM_WKB_PATH,
        meta_path: Path = GEO_META_JSON_PATH,
    ) -> None:
        with self._init_lock:
            if self.loaded:
                return
            self.features = load_features(features_path)
            index_payload = load_index(index_path)
            self.index_records = index_payload["records"]
            self.record_by_sub_id = {record.sub_id: record for record in self.index_records}
            self.grid_index = index_payload["grid_index"]
            self.subgrid_index = index_payload.get("subgrid_index", {})
            self.feature_parts = index_payload["feature_parts"]
            self.geometry_store = GeometryStore(geometry_path)
            self.meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            self._geometry_cache = LRUCache[int, object](GEO_CACHE_MAX_ITEMS)
            self.loaded = True

    def check_init_is_ok(self) -> None:
        if not self.loaded:
            raise RuntimeError("Geo query engine not initialized")
        if self.geometry_store is None:
            raise RuntimeError("Geometry store unavailable")

    def _load_geometry(self, record: SubGeometryIndexRecord) -> dict | None:
        cached = self._geometry_cache.get(record.sub_id)
        if cached is not None:
            return None if cached is _CACHE_SENTINEL else cached
        assert self.geometry_store is not None
        raw = self.geometry_store.read(record.geom_offset, record.geom_length)
        geometry = json.loads(raw.decode("utf-8")) if raw else None
        self._geometry_cache.put(record.sub_id, geometry if geometry is not None else _CACHE_SENTINEL)
        return geometry

    def cache_stats(self) -> dict[str, int]:
        return {
            "cache_max_items": self._geometry_cache.max_items,
            "cache_current_items": len(self._geometry_cache),
            "cache_hit_count": self._geometry_cache.hit_count,
            "cache_miss_count": self._geometry_cache.miss_count,
            "cache_eviction_count": self._geometry_cache.eviction_count,
        }

    def grid_candidates_for_bbox(self, bbox: tuple[float, float, float, float]) -> list[SubGeometryIndexRecord]:
        factor = int(self.meta.get("grid_factor", GEO_GRID_FACTOR))
        subgrid_factor = int(self.meta.get("subgrid_factor", factor))
        min_lng, min_lat, max_lng, max_lat = bbox
        x1 = int(min_lng * factor)
        x2 = int(max_lng * factor)
        y1 = int(min_lat * factor)
        y2 = int(max_lat * factor)
        sub_ids: set[int] = set()
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                sub_ids.update(self.grid_index.get(f"{x}:{y}", []))
        sx1 = int(min_lng * subgrid_factor)
        sx2 = int(max_lng * subgrid_factor)
        sy1 = int(min_lat * subgrid_factor)
        sy2 = int(max_lat * subgrid_factor)
        refined_ids: set[int] = set()
        for x in range(sx1, sx2 + 1):
            for y in range(sy1, sy2 + 1):
                refined_ids.update(self.subgrid_index.get(f"{x}:{y}", []))
        if refined_ids:
            sub_ids &= refined_ids
        return [self.record_by_sub_id[sub_id] for sub_id in sub_ids if sub_id in self.record_by_sub_id]

    def query_point(self, lng: float, lat: float, where: WhereFn = None) -> QueryResult:
        self.check_init_is_ok()
        return point_query(self, self._load_geometry, self.features, lng, lat, where)

    def query_point_with_tolerance(self, lng: float, lat: float, tolerance_metre: int = GEO_POINT_TOLERANCE_METRE, where: WhereFn = None) -> QueryResult:
        self.check_init_is_ok()
        return point_query_with_tolerance(self, self._load_geometry, self.features, lng, lat, tolerance_metre, where)

    def query_geometry(self, query_geometry_payload: dict, where: WhereFn = None) -> QueryResult:
        self.check_init_is_ok()
        return geometry_query(self, self._load_geometry, self.features, query_geometry_payload, where)

    def rebuild_feature_geometry(self, feature_id: int) -> dict | None:
        feature = self.features.get(feature_id)
        if not feature:
            return None
        sub_ids = self.feature_parts.get(feature_id, [])
        if not sub_ids:
            return None
        geometries = []
        seen_part_keys = set()
        for sub_id in sub_ids:
            record = self.record_by_sub_id.get(sub_id)
            if not record:
                continue
            part_key = (record.source_geometry_type, record.part_index)
            if part_key in seen_part_keys:
                continue
            seen_part_keys.add(part_key)
            geometry = self._load_geometry(record)
            if geometry:
                geometries.append(geometry)
        if not geometries:
            return None
        if feature.geometry_type == "Polygon":
            return geometries[0]
        if feature.geometry_type == "MultiPolygon":
            polygon_coords = []
            for geometry in geometries:
                if geometry.get("type") == "Polygon":
                    polygon_coords.append(geometry["coordinates"])
            if polygon_coords:
                return {"type": "MultiPolygon", "coordinates": polygon_coords}
        if len(geometries) == 1:
            return geometries[0]
        return {"type": "GeometryCollection", "geometries": geometries}

    def read_boundary_by_id(self, feature_id: int) -> dict | None:
        self.check_init_is_ok()
        feature = self.features.get(feature_id)
        if not feature:
            return None
        geometry = self.rebuild_feature_geometry(feature_id)
        return {"feature": feature.to_dict(), "geometry": geometry}

    def search(self, q: str, deep: int | None = None) -> list[dict]:
        self.check_init_is_ok()
        q = q.strip().lower()
        if not q:
            return []
        results = []
        for feature in self.features.values():
            if deep is not None and feature.deep != deep:
                continue
            if q in feature.name.lower() or q in feature.ext_path.lower():
                results.append(feature.to_dict())
        return results

    def children(self, parent_id: int | None = None, deep: int | None = None) -> list[dict]:
        self.check_init_is_ok()
        items = []
        for feature in self.features.values():
            if parent_id is not None and feature.pid != parent_id:
                continue
            if deep is not None and feature.deep != deep:
                continue
            items.append(feature.to_dict())
        items.sort(key=lambda item: (item["deep"], item["id"]))
        return items

    def get_status(self) -> EngineStatus:
        cache_stats = self.cache_stats()
        return EngineStatus(
            loaded=self.loaded,
            mode=self.mode,
            feature_count=len(self.features),
            subgeometry_count=len(self.index_records),
            features_with_multiple_parts=int(self.meta.get("features_with_multiple_parts", 0)),
            split_mode=self.meta.get("split_mode", "unknown"),
            source_crs=self.meta.get("source_crs", "unknown"),
            target_crs=self.meta.get("target_crs", "unknown"),
            storage_format=self.meta.get("storage_format", "unknown"),
            grid_factor=int(self.meta.get("grid_factor", GEO_GRID_FACTOR)),
            subgrid_factor=int(self.meta.get("subgrid_factor", self.meta.get("grid_factor", GEO_GRID_FACTOR))),
            cache_max_items=cache_stats["cache_max_items"],
            cache_current_items=cache_stats["cache_current_items"],
            cache_hit_count=cache_stats["cache_hit_count"],
            cache_miss_count=cache_stats["cache_miss_count"],
            cache_eviction_count=cache_stats["cache_eviction_count"],
            index_path=str(GEO_INDEX_JSON_PATH),
            features_path=str(GEO_FEATURES_JSONL_PATH),
            geometry_path=str(GEO_SUBGEOM_WKB_PATH),
        )


ENGINE = AreaCityQueryPy()
