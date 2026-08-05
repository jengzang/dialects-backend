#!/usr/bin/env python3
"""Build a single-file GIS index (gis.db) from the WGS84 GeoJSON source.

Produces one self-contained SQLite database with:
  - features       — administrative division metadata (id, name, pid, deep, center, etc.)
  - subgeometries  — per-polygon-part geometry stored as JSON BLOBs
  - subgeometry_rtree — RTree spatial index over subgeometry bounding boxes
  - feature_parts  — mapping from feature_id to its subgeometry ids
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/geo/generated/geojson/wgs84/areacity_full_level0-2.geojson"
OUT_DIR = ROOT / "data/dependency"
OUT_DB = OUT_DIR / "gis.db"


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
        CREATE TABLE features (
            id INTEGER PRIMARY KEY,
            pid INTEGER NOT NULL,
            deep INTEGER NOT NULL,
            name TEXT NOT NULL,
            ext_path TEXT NOT NULL,
            center_lng REAL,
            center_lat REAL,
            source_crs TEXT NOT NULL DEFAULT 'WGS84',
            target_crs TEXT NOT NULL DEFAULT 'WGS84',
            source_file TEXT NOT NULL,
            geometry_type TEXT,
            geometry_exists INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.execute("CREATE INDEX idx_features_pid ON features(pid)")
    conn.execute("CREATE INDEX idx_features_deep ON features(deep)")
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
            geom_blob BLOB NOT NULL
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

    conn = initialize_sqlite(OUT_DB)
    cur = conn.cursor()

    sub_id = 1
    subgeometry_count = 0
    features_with_geometry = 0
    features_with_multiple_parts = 0
    total_geom_bytes = 0

    for feature in features:
        props = dict(feature["properties"])
        props["geometry_type"] = feature["geometry"]["type"] if feature.get("geometry") else None
        props["geometry_exists"] = feature.get("geometry") is not None

        cur.execute(
            """
            INSERT INTO features (id, pid, deep, name, ext_path, center_lng, center_lat,
                                  source_crs, target_crs, source_file, geometry_type, geometry_exists)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                props["id"], props["pid"], props["deep"], props["name"], props["ext_path"],
                props["center_lng"], props["center_lat"],
                props.get("source_crs", "WGS84"), props.get("target_crs", "WGS84"),
                props.get("source_file", ""), props["geometry_type"],
                1 if props["geometry_exists"] else 0,
            ),
        )

        parts = split_geometry(props["id"], props["deep"], feature.get("geometry"))
        if parts:
            features_with_geometry += 1
            part_count_histogram[len(parts)] += 1
            if len(parts) > 1:
                features_with_multiple_parts += 1

        for part in parts:
            raw = json.dumps(part["geometry"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            total_geom_bytes += len(raw)
            min_lng, min_lat, max_lng, max_lat = part["bbox"]
            cur.execute(
                """
                INSERT INTO subgeometries (
                    sub_id, feature_id, deep, part_index, part_kind, source_geometry_type,
                    min_lng, min_lat, max_lng, max_lat, geom_blob
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sub_id, part["feature_id"], part["deep"], part["part_index"],
                    part["part_kind"], part["source_geometry_type"],
                    min_lng, min_lat, max_lng, max_lat,
                    raw,
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
            sub_id += 1
            subgeometry_count += 1

    conn.commit()

    manifest = {
        "source": str(SOURCE.relative_to(ROOT)),
        "source_crs": "WGS84",
        "feature_count": len(features),
        "subgeometry_count": subgeometry_count,
        "features_with_geometry": features_with_geometry,
        "features_with_multiple_parts": features_with_multiple_parts,
        "total_geom_bytes": total_geom_bytes,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "part_count_histogram": {str(k): v for k, v in sorted(part_count_histogram.items())},
        "part_kind_histogram": {str(k): v for k, v in sorted(part_kind_histogram.items())},
    }
    conn.execute(
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"
    )
    for k, v in manifest.items():
        conn.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (k, json.dumps(v, ensure_ascii=False)))
    conn.commit()
    conn.close()

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nProduced: {OUT_DB} ({OUT_DB.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
