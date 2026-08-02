from __future__ import annotations

import os
from pathlib import Path

from app.common.path import GIS_DATA_DIR

GEO_RUNTIME_DATA_DIR = Path(os.getenv("GIS_DATA_DIR", GIS_DATA_DIR))

GEO_INDEX_SQLITE_PATH = GEO_RUNTIME_DATA_DIR / "gis.db"

GEO_POINT_TOLERANCE_METRE = int(os.getenv("GEO_POINT_TOLERANCE_METRE", "2500"))
GEO_CACHE_MAX_ITEMS = int(os.getenv("GEO_CACHE_MAX_ITEMS", "2048"))
GEO_AUTO_BUILD_ON_STARTUP = os.getenv("GEO_AUTO_BUILD_ON_STARTUP", "1").strip() not in {"0", "false", "False"}
