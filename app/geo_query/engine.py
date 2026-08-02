from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from queue import Empty, Queue
from threading import Lock
from typing import Callable, Iterator

import sqlite3

from .cache import LRUCache
from .config import GEO_CACHE_MAX_ITEMS, GEO_INDEX_SQLITE_PATH, GEO_POINT_TOLERANCE_METRE
from .index_store import (
    load_feature_by_id,
    load_geometry_blob,
    load_meta,
    load_subgeometry_by_ids,
    query_candidate_records_by_bbox,
    query_children,
    query_feature_part_ids,
    search_features,
)
from .models import EngineStatus, QueryResult, SubGeometryIndexRecord
from .query_ops import geometry_query, point_query, point_query_with_tolerance

WhereFn = Callable[[dict], bool] | None
_CACHE_SENTINEL = object()


class _ReadOnlyPool:
    """Minimal read-only SQLite connection pool for the GIS index."""

    def __init__(self, db_path: Path, pool_size: int = 3):
        self._uri = f"file:{db_path}?mode=ro"
        self._pool: Queue[sqlite3.Connection] = Queue(maxsize=pool_size * 2)
        self._lock = Lock()
        self._created = 0
        self._max_conns = pool_size * 2

        for _ in range(pool_size):
            self._pool.put(self._create())
            self._created += 1

    def _create(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def get(self) -> Iterator[sqlite3.Connection]:
        conn = None
        try:
            try:
                conn = self._pool.get(timeout=5)
            except Empty:
                with self._lock:
                    if self._created < self._max_conns:
                        conn = self._create()
                        self._created += 1
                    else:
                        raise TimeoutError("GIS connection pool exhausted")
            yield conn
        finally:
            if conn is None:
                return
            try:
                conn.execute("SELECT 1")
                self._pool.put(conn, block=False)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                try:
                    self._pool.put(self._create(), block=False)
                except Exception:
                    pass


class AreaCityQueryPy:
    def __init__(self):
        self.loaded = False
        self._db_path: Path | None = None
        self._pool: _ReadOnlyPool | None = None
        self.meta: dict = {}
        self._geometry_cache = LRUCache[int, object](GEO_CACHE_MAX_ITEMS)
        self._init_lock = Lock()

    def init_store(self, index_db_path: Path = GEO_INDEX_SQLITE_PATH) -> None:
        with self._init_lock:
            if self.loaded:
                return
            pool = _ReadOnlyPool(index_db_path)
            with pool.get() as conn:
                self.meta = load_meta(conn)
            self._db_path = index_db_path
            self._pool = pool
            self._geometry_cache = LRUCache[int, object](GEO_CACHE_MAX_ITEMS)
            self.loaded = True

    def check_init_is_ok(self) -> None:
        if not self.loaded:
            raise RuntimeError("Geo query engine not initialized")
        if self._pool is None:
            raise RuntimeError("SQLite connection pool unavailable")

    def _get_conn(self):
        assert self._pool is not None
        return self._pool.get()

    def _load_geometry(self, conn: sqlite3.Connection, record: SubGeometryIndexRecord) -> dict | None:
        cached = self._geometry_cache.get(record.sub_id)
        if cached is not None:
            return None if cached is _CACHE_SENTINEL else cached
        raw = load_geometry_blob(conn, record.sub_id)
        if raw is None:
            self._geometry_cache.put(record.sub_id, _CACHE_SENTINEL)
            return None
        geometry = json.loads(raw.decode("utf-8"))
        self._geometry_cache.put(record.sub_id, geometry)
        return geometry

    def cache_stats(self) -> dict[str, int]:
        return {
            "cache_max_items": self._geometry_cache.max_items,
            "cache_current_items": len(self._geometry_cache),
            "cache_hit_count": self._geometry_cache.hit_count,
            "cache_miss_count": self._geometry_cache.miss_count,
            "cache_eviction_count": self._geometry_cache.eviction_count,
        }

    # --- query endpoints ---

    def grid_candidates_for_bbox(self, conn: sqlite3.Connection, bbox: tuple[float, float, float, float]) -> list[SubGeometryIndexRecord]:
        return query_candidate_records_by_bbox(conn, bbox)

    def query_point(self, lng: float, lat: float, where: WhereFn = None) -> QueryResult:
        self.check_init_is_ok()
        with self._get_conn() as conn:
            return point_query(self, self._load_geometry, conn, lng, lat, where)

    def query_point_with_tolerance(self, lng: float, lat: float, tolerance_metre: int = GEO_POINT_TOLERANCE_METRE, where: WhereFn = None) -> QueryResult:
        self.check_init_is_ok()
        with self._get_conn() as conn:
            return point_query_with_tolerance(self, self._load_geometry, conn, lng, lat, tolerance_metre, where)

    def query_geometry(self, query_geometry_payload: dict, where: WhereFn = None) -> QueryResult:
        self.check_init_is_ok()
        with self._get_conn() as conn:
            return geometry_query(self, self._load_geometry, conn, query_geometry_payload, where)

    # --- boundary ---

    def rebuild_feature_geometry(self, feature_id: int) -> dict | None:
        self.check_init_is_ok()
        with self._get_conn() as conn:
            feature = load_feature_by_id(conn, feature_id)
            if not feature:
                return None
            sub_ids = query_feature_part_ids(conn, feature_id)
            records = load_subgeometry_by_ids(conn, sub_ids)
            if not records:
                return None
            geometries = []
            seen_part_keys = set()
            for record in records:
                part_key = (record.source_geometry_type, record.part_index)
                if part_key in seen_part_keys:
                    continue
                seen_part_keys.add(part_key)
                geometry = self._load_geometry(conn, record)
                if geometry:
                    geometries.append(geometry)

        if not geometries:
            return None
        if feature.geometry_type == "Polygon":
            return geometries[0]
        if feature.geometry_type == "MultiPolygon":
            polygon_coords = [g["coordinates"] for g in geometries if g.get("type") == "Polygon"]
            return {"type": "MultiPolygon", "coordinates": polygon_coords} if polygon_coords else None
        if len(geometries) == 1:
            return geometries[0]
        return {"type": "GeometryCollection", "geometries": geometries}

    def read_boundary_by_id(self, feature_id: int) -> dict | None:
        self.check_init_is_ok()
        with self._get_conn() as conn:
            feature = load_feature_by_id(conn, feature_id)
        if not feature:
            return None
        geometry = self.rebuild_feature_geometry(feature_id)
        return {"feature": feature.to_dict(), "geometry": geometry}

    # --- search / children / resolve ---

    def search(self, q: str, deep: int | None = None) -> list[dict]:
        self.check_init_is_ok()
        q = q.strip()
        if not q:
            return []
        with self._get_conn() as conn:
            return [f.to_dict() for f in search_features(conn, q, deep)]

    def feature_path(self, feature_id: int) -> list[dict]:
        self.check_init_is_ok()
        with self._get_conn() as conn:
            path = []
            current = load_feature_by_id(conn, feature_id)
            seen_ids = set()
            while current is not None and current.id not in seen_ids:
                seen_ids.add(current.id)
                path.append({"id": current.id, "name": current.name, "deep": current.deep})
                if current.pid == 0:
                    break
                current = load_feature_by_id(conn, current.pid)
        path.reverse()
        return path

    def feature_to_resolved_dict(self, conn: sqlite3.Connection, feature_id: int) -> dict | None:
        feature = load_feature_by_id(conn, feature_id)
        if feature is None:
            return None
        item = feature.to_dict()
        path = self._feature_path_for(conn, feature)
        item["path"] = path
        path_by_deep = {part["deep"]: part["name"] for part in path}
        item["path_names"] = {
            "province": path_by_deep.get(0),
            "city": path_by_deep.get(1),
            "county": path_by_deep.get(2),
        }
        return item

    def _feature_path_for(self, conn: sqlite3.Connection, feature: object) -> list[dict]:
        path = []
        current = feature
        seen_ids = set()
        while current is not None and current.id not in seen_ids:
            seen_ids.add(current.id)
            path.append({"id": current.id, "name": current.name, "deep": current.deep})
            if current.pid == 0:
                break
            current = load_feature_by_id(conn, current.pid)
        path.reverse()
        return path

    def resolve(
        self,
        *,
        province: str | None = None,
        city: str | None = None,
        county: str | None = None,
        path: str | None = None,
    ) -> dict:
        self.check_init_is_ok()
        requested_parts = self._resolve_requested_parts(province=province, city=city, county=county, path=path)
        if not requested_parts:
            return {"success": True, "matched": False, "ambiguous": False, "feature": None, "candidates": []}

        with self._get_conn() as conn:
            target_name = requested_parts[-1].lower()
            rows = conn.execute(
                "SELECT id FROM features WHERE LOWER(name) = ?",
                (target_name,),
            ).fetchall()

            candidates = []
            for row in rows:
                feat = load_feature_by_id(conn, int(row["id"]))
                if feat is None:
                    continue
                feat_path = self._feature_path_for(conn, feat)
                names = [p["name"] for p in feat_path]
                if self._path_matches_request(requested_parts, names):
                    resolved = self.feature_to_resolved_dict(conn, feat.id)
                    if resolved:
                        candidates.append(resolved)

        if len(candidates) == 1:
            return {"success": True, "matched": True, "ambiguous": False, "feature": candidates[0], "candidates": []}
        return {
            "success": True,
            "matched": False,
            "ambiguous": len(candidates) > 1,
            "feature": None,
            "candidates": candidates,
        }

    @staticmethod
    def _path_matches_request(requested_parts: list[str], names: list[str]) -> bool:
        if names == requested_parts:
            return True
        if len(requested_parts) == 2 and len(names) == 3 and names[0] == names[1] == requested_parts[0] and names[2] == requested_parts[1]:
            return True
        if len(requested_parts) == 1:
            return names[-1] == requested_parts[0]
        return False

    def _resolve_requested_parts(
        self,
        *,
        province: str | None,
        city: str | None,
        county: str | None,
        path: str | None,
    ) -> list[str]:
        if path is not None and path.strip():
            return [part.strip() for part in path.replace(">", "/").split("/") if part.strip()]
        return [part.strip() for part in (province, city, county) if part is not None and part.strip()]

    def children(self, parent_id: int | None = None, deep: int | None = None) -> list[dict]:
        self.check_init_is_ok()
        with self._get_conn() as conn:
            return [f.to_dict() for f in query_children(conn, parent_id, deep)]

    def get_status(self) -> EngineStatus:
        self.check_init_is_ok()
        cache_stats = self.cache_stats()
        with self._get_conn() as conn:
            feature_count = conn.execute("SELECT COUNT(*) FROM features").fetchone()[0]
        return EngineStatus(
            loaded=self.loaded,
            mode="sqlite",
            feature_count=feature_count,
            subgeometry_count=int(self.meta.get("subgeometry_count", 0)),
            features_with_multiple_parts=int(self.meta.get("features_with_multiple_parts", 0)),
            split_mode="polygon-parts-rtree-v1",
            source_crs="WGS84",
            target_crs="WGS84",
            storage_format="geojson-bytes",
            grid_factor=0,
            subgrid_factor=0,
            cache_max_items=cache_stats["cache_max_items"],
            cache_current_items=cache_stats["cache_current_items"],
            cache_hit_count=cache_stats["cache_hit_count"],
            cache_miss_count=cache_stats["cache_miss_count"],
            cache_eviction_count=cache_stats["cache_eviction_count"],
            index_path=str(self._db_path) if self._db_path else str(GEO_INDEX_SQLITE_PATH),
            features_path="n/a (in sqlite)",
            geometry_path="n/a (in sqlite)",
        )


ENGINE = AreaCityQueryPy()
