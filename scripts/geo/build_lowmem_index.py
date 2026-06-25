#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/geo/generated/geojson/wgs84/areacity_full_level0-2.geojson"
OUT_DIR = ROOT / "data/geo/generated/engine/wgs84"
INDEX_PATH = OUT_DIR / "areacity.index.json"
FEATURES_PATH = OUT_DIR / "areacity.features.jsonl"
GEOM_PATH = OUT_DIR / "areacity.subgeom.bin"
META_PATH = OUT_DIR / "areacity.meta.json"
MANIFEST_PATH = OUT_DIR / "areacity.build_manifest.json"
GRID_FACTOR = 100
STORAGE_FORMAT = "geojson-bytes"
SPLIT_MODE = "polygon-parts-gridrefs-v1"
SUBGRID_FACTOR = 500


def geometry_bbox(geometry: dict | None):
    if not geometry:
        return None
    min_lng = float("inf")
    min_lat = float("inf")
    max_lng = float("-inf")
    max_lat = float("-inf")

    def walk(obj):
        nonlocal min_lng, min_lat, max_lng, max_lat
        if isinstance(obj, (list, tuple)) and obj and isinstance(obj[0], (int, float)):
            lng = float(obj[0])
            lat = float(obj[1])
            min_lng = min(min_lng, lng)
            min_lat = min(min_lat, lat)
            max_lng = max(max_lng, lng)
            max_lat = max(max_lat, lat)
            return
        if isinstance(obj, (list, tuple)):
            for item in obj:
                walk(item)

    walk(geometry.get("coordinates", []))
    if min_lng == float("inf"):
        return None
    return min_lng, min_lat, max_lng, max_lat


def grid_cells_for_bbox(bbox: tuple[float, float, float, float], factor: int) -> list[str]:
    min_lng, min_lat, max_lng, max_lat = bbox
    x1 = int(min_lng * factor)
    x2 = int(max_lng * factor)
    y1 = int(min_lat * factor)
    y2 = int(max_lat * factor)
    cells = []
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            cells.append(f"{x}:{y}")
    return cells


def polygon_geometries(geometry: dict | None) -> list[dict]:
    if not geometry:
        return []
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        return [{"type": "Polygon", "coordinates": coords}]
    if gtype == "MultiPolygon":
        return [{"type": "Polygon", "coordinates": polygon} for polygon in coords]
    return []


def split_geometry(feature_id: int, deep: int, geometry: dict | None) -> list[dict[str, Any]]:
    polygons = polygon_geometries(geometry)
    if not polygons:
        return []
    parts: list[dict[str, Any]] = []
    for idx, polygon in enumerate(polygons, start=1):
        bbox = geometry_bbox(polygon)
        if bbox is None:
            continue
        parts.append(
            {
                "feature_id": feature_id,
                "deep": deep,
                "part_index": idx,
                "part_kind": "polygon",
                "source_geometry_type": "Polygon",
                "bbox": bbox,
                "geometry": polygon,
                "grid_refs": grid_cells_for_bbox(bbox, GRID_FACTOR),
                "subgrid_refs": grid_cells_for_bbox(bbox, SUBGRID_FACTOR),
            }
        )
    return parts


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    features = source["features"]

    part_count_histogram: dict[int, int] = defaultdict(int)
    part_kind_histogram: dict[str, int] = defaultdict(int)
    subgrid_span_histogram: dict[int, int] = defaultdict(int)
    feature_rows: list[str] = []
    geom_blobs: list[bytes] = []
    index_records: list[dict[str, Any]] = []
    grid_index: dict[str, list[int]] = defaultdict(list)
    subgrid_index: dict[str, list[int]] = defaultdict(list)
    feature_parts: dict[int, list[int]] = defaultdict(list)

    sub_id = 1
    offset = 0
    features_with_geometry = 0
    features_with_multiple_parts = 0

    for feature in features:
        props = dict(feature["properties"])
        props["geometry_type"] = feature["geometry"]["type"] if feature.get("geometry") else None
        props["geometry_exists"] = feature.get("geometry") is not None
        feature_rows.append(json.dumps(props, ensure_ascii=False))

        parts = split_geometry(props["id"], props["deep"], feature.get("geometry"))
        if parts:
            features_with_geometry += 1
            part_count_histogram[len(parts)] += 1
            if len(parts) > 1:
                features_with_multiple_parts += 1
        for part in parts:
            raw = json.dumps(part["geometry"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            geom_blobs.append(raw)
            record = {
                "sub_id": sub_id,
                "feature_id": part["feature_id"],
                "deep": part["deep"],
                "part_index": part["part_index"],
                "part_kind": part["part_kind"],
                "source_geometry_type": part["source_geometry_type"],
                "bbox": list(part["bbox"]),
                "geom_offset": offset,
                "geom_length": len(raw),
                "subgrid_refs": part["subgrid_refs"],
            }
            index_records.append(record)
            part_kind_histogram[part["part_kind"]] += 1
            subgrid_span_histogram[len(part["subgrid_refs"])] += 1
            feature_parts[part["feature_id"]].append(sub_id)
            for grid_ref in part["grid_refs"]:
                grid_index[grid_ref].append(sub_id)
            for subgrid_ref in part["subgrid_refs"]:
                subgrid_index[subgrid_ref].append(sub_id)
            offset += len(raw)
            sub_id += 1

    manifest = {
        "source": str(SOURCE.relative_to(ROOT)),
        "grid_factor": GRID_FACTOR,
        "subgrid_factor": SUBGRID_FACTOR,
        "storage_format": STORAGE_FORMAT,
        "split_mode": SPLIT_MODE,
        "source_crs": "WGS84",
        "target_crs": "WGS84",
        "feature_count": len(features),
        "subgeometry_count": len(index_records),
        "features_with_geometry": features_with_geometry,
        "features_with_multiple_parts": features_with_multiple_parts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "part_count_histogram": {str(k): v for k, v in sorted(part_count_histogram.items())},
        "part_kind_histogram": {str(k): v for k, v in sorted(part_kind_histogram.items())},
        "subgrid_span_histogram": {str(k): v for k, v in sorted(subgrid_span_histogram.items())},
    }
    payload = {
        "subgeometries": index_records,
        "grid_index": grid_index,
        "subgrid_index": subgrid_index,
        "feature_parts": feature_parts,
    }

    FEATURES_PATH.write_text("\n".join(feature_rows) + "\n", encoding="utf-8")
    with GEOM_PATH.open("wb") as f_geom:
        for blob in geom_blobs:
            f_geom.write(blob)
    with INDEX_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    META_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
