#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/geo/generated/geojson/wgs84/areacity_full_level0-2.geojson"
OUT_DIR = ROOT / "data/geo/generated/engine/wgs84"
INDEX_SQLITE_PATH = OUT_DIR / "areacity.index.sqlite"
FEATURES_PATH = OUT_DIR / "areacity.features.jsonl"
GEOM_PATH = OUT_DIR / "areacity.subgeom.bin"
META_PATH = OUT_DIR / "areacity.meta.json"
MANIFEST_PATH = OUT_DIR / "areacity.build_manifest.json"
GRID_FACTOR = 100
STORAGE_FORMAT = "geojson-bytes"
SPLIT_MODE = "polygon-parts-rtree-v1"
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
                "subgrid_refs": [],
            }
        )
    return parts


def initialize_sqlite(path: Path) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute(
        """
        CREATE TABLE subgeometries (
            sub_id INTEGER PRIMARY KEY,
            feature_id INTEGER NOT NULL,
            deep INTEGER NOT NULL,
            part_index INTEGER NOT NULL,
            part_kind TEXT NOT NULL,
            source_geometry_type TEXT NOT NULL,
            min_lng REAL NOT NULL,
            min_lat REAL NOT NULL,
            max_lng REAL NOT NULL,
            max_lat REAL NOT NULL,
            geom_offset INTEGER NOT NULL,
            geom_length INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE subgeometry_rtree USING rtree(
            sub_id,
            min_lng, max_lng,
            min_lat, max_lat
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE feature_parts (
            feature_id INTEGER NOT NULL,
            sub_id INTEGER NOT NULL,
            part_index INTEGER NOT NULL,
            PRIMARY KEY (feature_id, sub_id)
        )
        """
    )
    conn.execute("CREATE INDEX idx_feature_parts_feature_id ON feature_parts(feature_id)")
    return conn


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    features = source["features"]

    part_count_histogram: dict[int, int] = defaultdict(int)
    part_kind_histogram: dict[str, int] = defaultdict(int)
    subgrid_span_histogram: dict[int, int] = defaultdict(int)
    feature_rows: list[str] = []
    geom_blobs: list[bytes] = []

    conn = initialize_sqlite(INDEX_SQLITE_PATH)
    cur = conn.cursor()

    sub_id = 1
    offset = 0
    subgeometry_count = 0
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
            min_lng, min_lat, max_lng, max_lat = part["bbox"]
            cur.execute(
                """
                INSERT INTO subgeometries (
                    sub_id, feature_id, deep, part_index, part_kind, source_geometry_type,
                    min_lng, min_lat, max_lng, max_lat, geom_offset, geom_length
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sub_id,
                    part["feature_id"],
                    part["deep"],
                    part["part_index"],
                    part["part_kind"],
                    part["source_geometry_type"],
                    min_lng,
                    min_lat,
                    max_lng,
                    max_lat,
                    offset,
                    len(raw),
                ),
            )
            cur.execute(
                "INSERT INTO subgeometry_rtree (sub_id, min_lng, max_lng, min_lat, max_lat) VALUES (?, ?, ?, ?, ?)",
                (sub_id, min_lng, max_lng, min_lat, max_lat),
            )
            cur.execute(
                "INSERT INTO feature_parts (feature_id, sub_id, part_index) VALUES (?, ?, ?)",
                (part["feature_id"], sub_id, part["part_index"]),
            )
            part_kind_histogram[part["part_kind"]] += 1
            subgrid_span_histogram[len(part["subgrid_refs"])] += 1
            offset += len(raw)
            sub_id += 1
            subgeometry_count += 1

    conn.commit()
    conn.close()

    manifest = {
        "source": str(SOURCE.relative_to(ROOT)),
        "grid_factor": GRID_FACTOR,
        "subgrid_factor": SUBGRID_FACTOR,
        "storage_format": STORAGE_FORMAT,
        "index_storage": "sqlite",
        "index_db_path": str(INDEX_SQLITE_PATH.relative_to(ROOT)),
        "split_mode": SPLIT_MODE,
        "source_crs": "WGS84",
        "target_crs": "WGS84",
        "feature_count": len(features),
        "subgeometry_count": subgeometry_count,
        "features_with_geometry": features_with_geometry,
        "features_with_multiple_parts": features_with_multiple_parts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "part_count_histogram": {str(k): v for k, v in sorted(part_count_histogram.items())},
        "part_kind_histogram": {str(k): v for k, v in sorted(part_kind_histogram.items())},
        "subgrid_span_histogram": {str(k): v for k, v in sorted(subgrid_span_histogram.items())},
    }

    FEATURES_PATH.write_text("\n".join(feature_rows) + "\n", encoding="utf-8")
    with GEOM_PATH.open("wb") as f_geom:
        for blob in geom_blobs:
            f_geom.write(blob)
    META_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
