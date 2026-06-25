from __future__ import annotations

from .geometry_utils import (
    bbox_intersects,
    geometry_bbox,
    geometry_intersects_geometry,
    metres_to_degree_buffer,
    point_bbox,
    point_in_geometry,
    point_to_geometry_distance_metres,
)
from .models import QueryResult


def _apply_cache_stats(engine, result: QueryResult, base_hits: int, base_misses: int, base_evictions: int) -> None:
    cache_stats = engine.cache_stats()
    result.stats.cache_hit_count = cache_stats["cache_hit_count"] - base_hits
    result.stats.cache_miss_count = cache_stats["cache_miss_count"] - base_misses
    result.stats.cache_eviction_count = cache_stats["cache_eviction_count"] - base_evictions


def filter_candidates(engine, query_bbox):
    candidates = engine.grid_candidates_for_bbox(query_bbox)
    if not candidates:
        candidates = engine.index_records
    return [record for record in candidates if bbox_intersects(record.bbox, query_bbox)]


def point_query(engine, geometry_loader, feature_records, lng: float, lat: float, where=None) -> QueryResult:
    res = QueryResult()
    res.stats.query_count += 1
    base_cache = engine.cache_stats()
    candidates = filter_candidates(engine, point_bbox(lng, lat))
    res.stats.envelope_hit_count += len(candidates)
    matched = set()
    for record in candidates:
        feature = feature_records[record.feature_id]
        data = feature.to_dict()
        if where and not where(data):
            continue
        geom = geometry_loader(record)
        if geom is None:
            continue
        res.stats.io_reads += 1
        if point_in_geometry(lng, lat, geom) and feature.id not in matched:
            matched.add(feature.id)
            res.result.append(data)
            res.stats.exact_hit_count += 1
    _apply_cache_stats(engine, res, base_cache["cache_hit_count"], base_cache["cache_miss_count"], base_cache["cache_eviction_count"])
    return res


def geometry_query(engine, geometry_loader, feature_records, query_geometry: dict, where=None) -> QueryResult:
    res = QueryResult()
    res.stats.query_count += 1
    base_cache = engine.cache_stats()
    bbox = geometry_bbox(query_geometry)
    if bbox is None:
        _apply_cache_stats(engine, res, base_cache["cache_hit_count"], base_cache["cache_miss_count"], base_cache["cache_eviction_count"])
        return res
    candidates = filter_candidates(engine, bbox)
    res.stats.envelope_hit_count += len(candidates)
    matched = set()
    for record in candidates:
        feature = feature_records[record.feature_id]
        data = feature.to_dict()
        if where and not where(data):
            continue
        geom = geometry_loader(record)
        if geom is None:
            continue
        res.stats.io_reads += 1
        if geometry_intersects_geometry(query_geometry, geom) and feature.id not in matched:
            matched.add(feature.id)
            res.result.append(data)
            res.stats.exact_hit_count += 1
    _apply_cache_stats(engine, res, base_cache["cache_hit_count"], base_cache["cache_miss_count"], base_cache["cache_eviction_count"])
    return res


def point_query_with_tolerance(engine, geometry_loader, feature_records, lng: float, lat: float, tolerance_metre: int, where=None) -> QueryResult:
    direct = point_query(engine, geometry_loader, feature_records, lng, lat, where)
    if direct.result or tolerance_metre == 0:
        return direct

    base_cache = engine.cache_stats()
    buffer_deg = metres_to_degree_buffer(tolerance_metre)
    query_bbox = (lng - buffer_deg, lat - buffer_deg, lng + buffer_deg, lat + buffer_deg)
    candidates = filter_candidates(engine, query_bbox)
    best_by_deep: dict[int, tuple[float, dict]] = {}
    for record in candidates:
        feature = feature_records[record.feature_id]
        data = feature.to_dict()
        if where and not where(data):
            continue
        geom = geometry_loader(record)
        if geom is None:
            continue
        direct.stats.io_reads += 1
        dist = point_to_geometry_distance_metres(lng, lat, geom)
        if tolerance_metre > 0 and dist > tolerance_metre:
            continue
        cur = best_by_deep.get(feature.deep)
        enriched = dict(data)
        enriched["point_distance"] = round(dist, 2)
        enriched["point_distance_id"] = feature.id
        if cur is None or dist < cur[0]:
            best_by_deep[feature.deep] = (dist, enriched)
    direct.result = [v[1] for v in sorted(best_by_deep.values(), key=lambda x: (x[1]["deep"], x[0]))]
    direct.stats.nearest_hit_count = len(direct.result)
    cache_stats = engine.cache_stats()
    direct.stats.cache_hit_count += cache_stats["cache_hit_count"] - base_cache["cache_hit_count"]
    direct.stats.cache_miss_count += cache_stats["cache_miss_count"] - base_cache["cache_miss_count"]
    direct.stats.cache_eviction_count += cache_stats["cache_eviction_count"] - base_cache["cache_eviction_count"]
    return direct
