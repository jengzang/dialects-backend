from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Callable

from .cache import LRUCache
from .config import (
    GEO_CACHE_MAX_ITEMS,
    GEO_FEATURES_JSONL_PATH,
    GEO_GRID_FACTOR,
    GEO_INDEX_SQLITE_PATH,
    GEO_META_JSON_PATH,
    GEO_POINT_TOLERANCE_METRE,
    GEO_SUBGEOM_WKB_PATH,
)
from .geometry_store import GeometryStore
from .index_store import (
    connect_index_db,
    count_subgeometries,
    load_features,
    load_subgeometry_by_ids,
    query_candidate_records_by_bbox,
    query_feature_part_ids,
)
from .models import EngineStatus, QueryResult, SubGeometryIndexRecord
from .query_ops import geometry_query, point_query, point_query_with_tolerance

WhereFn = Callable[[dict], bool] | None
_CACHE_SENTINEL = object()


class AreaCityQueryPy:
    def __init__(self):
        self.loaded = False
        self.mode = "lowmem-sqlite"
        self.features = {}
        self.index_records: list[SubGeometryIndexRecord] = []
        self.record_by_sub_id: dict[int, SubGeometryIndexRecord] = {}
        self.index_db_path: Path | None = None
        self.geometry_store: GeometryStore | None = None
        self.meta: dict = {}
        self._geometry_cache = LRUCache[int, object](GEO_CACHE_MAX_ITEMS)
        self._init_lock = Lock()

    def init_store_in_wkb_file(
        self,
        index_db_path: Path = GEO_INDEX_SQLITE_PATH,
        features_path: Path = GEO_FEATURES_JSONL_PATH,
        geometry_path: Path = GEO_SUBGEOM_WKB_PATH,
        meta_path: Path = GEO_META_JSON_PATH,
    ) -> None:
        with self._init_lock:
            if self.loaded:
                return
            self.features = load_features(features_path)
            conn = connect_index_db(index_db_path)
            try:
                subgeometry_count = count_subgeometries(conn)
            finally:
                conn.close()
            self.index_records = []
            self.record_by_sub_id = {}
            self.index_db_path = index_db_path
            self.geometry_store = GeometryStore(geometry_path)
            self.meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            if "subgeometry_count" not in self.meta:
                self.meta["subgeometry_count"] = subgeometry_count
            self._geometry_cache = LRUCache[int, object](GEO_CACHE_MAX_ITEMS)
            self.loaded = True

    def check_init_is_ok(self) -> None:
        if not self.loaded:
            raise RuntimeError("Geo query engine not initialized")
        if self.geometry_store is None:
            raise RuntimeError("Geometry store unavailable")
        if self.index_db_path is None:
            raise RuntimeError("SQLite index store unavailable")

    def _connect_index_db(self) -> sqlite3.Connection:
        assert self.index_db_path is not None
        return connect_index_db(self.index_db_path)

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
        self.check_init_is_ok()
        conn = self._connect_index_db()
        try:
            return query_candidate_records_by_bbox(conn, bbox)
        finally:
            conn.close()

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
        conn = self._connect_index_db()
        try:
            sub_ids = query_feature_part_ids(conn, feature_id)
            records = load_subgeometry_by_ids(conn, sub_ids)
        finally:
            conn.close()
        if not records:
            return None
        geometries = []
        seen_part_keys = set()
        for record in records:
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
            subgeometry_count=int(self.meta.get("subgeometry_count", 0)),
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
            index_path=str(self.index_db_path) if self.index_db_path else str(GEO_INDEX_SQLITE_PATH),
            features_path=str(GEO_FEATURES_JSONL_PATH),
            geometry_path=str(GEO_SUBGEOM_WKB_PATH),
        )


ENGINE = AreaCityQueryPy()
