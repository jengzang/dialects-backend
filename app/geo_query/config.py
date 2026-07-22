from __future__ import annotations

import os
from pathlib import Path

from app.common.path import GIS_DATA_DIR

GEO_RUNTIME_DATA_DIR = Path(os.getenv("GIS_DATA_DIR", GIS_DATA_DIR))

GEO_INDEX_SQLITE_PATH = GEO_RUNTIME_DATA_DIR / "areacity.index.sqlite"
GEO_FEATURES_JSONL_PATH = GEO_RUNTIME_DATA_DIR / "areacity.features.jsonl"
GEO_SUBGEOM_WKB_PATH = GEO_RUNTIME_DATA_DIR / "areacity.subgeom.bin"
GEO_META_JSON_PATH = GEO_RUNTIME_DATA_DIR / "areacity.meta.json"
GEO_ENGINE_MANIFEST_JSON_PATH = GEO_RUNTIME_DATA_DIR / "areacity.build_manifest.json"

GEO_GRID_FACTOR = int(os.getenv("GEO_GRID_FACTOR", "100"))
GEO_POINT_TOLERANCE_METRE = int(os.getenv("GEO_POINT_TOLERANCE_METRE", "2500"))
GEO_CACHE_MAX_ITEMS = int(os.getenv("GEO_CACHE_MAX_ITEMS", "2048"))
GEO_AUTO_BUILD_ON_STARTUP = os.getenv("GEO_AUTO_BUILD_ON_STARTUP", "1").strip() not in {"0", "false", "False"}
