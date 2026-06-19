#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/geo/source/ok_geo.csv"
OUT_DIR = ROOT / "data/geo/generated/geojson/wgs84"
MANIFEST = ROOT / "data/geo/generated/manifest/areacity_geojson_manifest.json"
LOG = ROOT / "data/geo/generated/logs/convert.log"

PI = math.pi
A = 6378245.0
EE = 0.00669342162296594323


def out_of_china(lng: float, lat: float) -> bool:
    return not (73.66 < lng < 135.05 and 3.86 < lat < 53.55)


def transform_lat(lng: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * PI) + 40.0 * math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * PI) + 320 * math.sin(lat * PI / 30.0)) * 2.0 / 3.0
    return ret


def transform_lng(lng: float, lat: float) -> float:
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * PI) + 40.0 * math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * PI) + 300.0 * math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    if out_of_china(lng, lat):
        return lng, lat
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    mg_lat = lat + dlat
    mg_lng = lng + dlng
    return lng * 2 - mg_lng, lat * 2 - mg_lat


def parse_coord_pair(pair: str) -> tuple[float, float]:
    lng_str, lat_str = pair.strip().split()
    return float(lng_str), float(lat_str)


def convert_ring(raw_ring: str) -> list[list[float]]:
    coords = []
    for pair in raw_ring.split(","):
        lng, lat = parse_coord_pair(pair)
        wgs_lng, wgs_lat = gcj02_to_wgs84(lng, lat)
        coords.append([round(wgs_lng, 6), round(wgs_lat, 6)])
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def polygon_to_geometry(polygon_text: str) -> dict:
    parts = [p for p in polygon_text.split(";") if p.strip()]
    polygons = []
    for part in parts:
        rings = [r for r in part.split("~") if r.strip()]
        polygon = [convert_ring(ring) for ring in rings]
        polygons.append(polygon)
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def point_to_wgs84(geo_text: str) -> tuple[float | None, float | None]:
    if geo_text.strip().upper() == "EMPTY":
        return None, None
    lng, lat = parse_coord_pair(geo_text)
    wgs_lng, wgs_lat = gcj02_to_wgs84(lng, lat)
    return round(wgs_lng, 6), round(wgs_lat, 6)


def feature_from_row(row: dict[str, str]) -> dict:
    center_lng, center_lat = point_to_wgs84(row["geo"])
    geometry = None if row["polygon"].strip().upper() == "EMPTY" else polygon_to_geometry(row["polygon"])
    return {
        "type": "Feature",
        "properties": {
            "id": int(row["id"]),
            "pid": int(row["pid"]),
            "deep": int(row["deep"]),
            "name": row["name"],
            "ext_path": row["ext_path"],
            "center_lng": center_lng,
            "center_lat": center_lat,
            "source_crs": "GCJ-02",
            "target_crs": "WGS84",
            "source_file": "data/geo/source/ok_geo.csv",
        },
        "geometry": geometry,
    }


def dump_geojson(path: Path, features: Iterable[dict]) -> int:
    feature_list = list(features)
    payload = {"type": "FeatureCollection", "features": feature_list}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return len(feature_list)


def main() -> None:
    csv.field_size_limit(sys.maxsize)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)

    by_deep: dict[int, list[dict]] = defaultdict(list)
    all_features: list[dict] = []
    total_rows = 0
    polygon_empty = 0
    geo_empty = 0

    with SOURCE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            if row["geo"].strip().upper() == "EMPTY":
                geo_empty += 1
            if row["polygon"].strip().upper() == "EMPTY":
                polygon_empty += 1
            feature = feature_from_row(row)
            all_features.append(feature)
            by_deep[int(row["deep"])] .append(feature)

    files = {}
    full_path = OUT_DIR / "areacity_full_level0-2.geojson"
    files[str(full_path.relative_to(ROOT))] = dump_geojson(full_path, all_features)
    for deep in sorted(by_deep):
        level_path = OUT_DIR / f"areacity_level{deep}.geojson"
        files[str(level_path.relative_to(ROOT))] = dump_geojson(level_path, by_deep[deep])

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(SOURCE.relative_to(ROOT)),
        "source_crs": "GCJ-02",
        "target_crs": "WGS84",
        "total_rows": total_rows,
        "geo_empty_count": geo_empty,
        "polygon_empty_count": polygon_empty,
        "output_files": files,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
