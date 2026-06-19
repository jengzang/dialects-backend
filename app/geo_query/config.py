from __future__ import annotations

import os
from pathlib import Path

from app.common.path import BASE_DIR

GEO_BASE_DIR = Path(BASE_DIR) / "data" / "geo"
GEO_SOURCE_DIR = GEO_BASE_DIR / "source"
GEO_GENERATED_DIR = GEO_BASE_DIR / "generated"
GEO_GEOJSON_WGS84_DIR = GEO_GENERATED_DIR / "geojson" / "wgs84"
GEO_ENGINE_WGS84_DIR = GEO_GENERATED_DIR / "engine" / "wgs84"

GEO_FULL_GEOJSON_PATH = GEO_GEOJSON_WGS84_DIR / "areacity_full_level0-2.geojson"
GEO_LEVEL0_GEOJSON_PATH = GEO_GEOJSON_WGS84_DIR / "areacity_level0.geojson"
GEO_LEVEL1_GEOJSON_PATH = GEO_GEOJSON_WGS84_DIR / "areacity_level1.geojson"
GEO_LEVEL2_GEOJSON_PATH = GEO_GEOJSON_WGS84_DIR / "areacity_level2.geojson"

GEO_INDEX_JSON_PATH = GEO_ENGINE_WGS84_DIR / "areacity.index.json"
GEO_FEATURES_JSONL_PATH = GEO_ENGINE_WGS84_DIR / "areacity.features.jsonl"
GEO_SUBGEOM_WKB_PATH = GEO_ENGINE_WGS84_DIR / "areacity.subgeom.bin"
GEO_META_JSON_PATH = GEO_ENGINE_WGS84_DIR / "areacity.meta.json"
GEO_ENGINE_MANIFEST_JSON_PATH = GEO_ENGINE_WGS84_DIR / "areacity.build_manifest.json"

GEO_GRID_FACTOR = int(os.getenv("GEO_GRID_FACTOR", "100"))
GEO_POINT_TOLERANCE_METRE = int(os.getenv("GEO_POINT_TOLERANCE_METRE", "2500"))
GEO_CACHE_MAX_ITEMS = int(os.getenv("GEO_CACHE_MAX_ITEMS", "2048"))
GEO_AUTO_BUILD_ON_STARTUP = os.getenv("GEO_AUTO_BUILD_ON_STARTUP", "1").strip() not in {"0", "false", "False"}
