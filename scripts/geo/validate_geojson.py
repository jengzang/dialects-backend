#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/geo/generated/geojson/wgs84"
MANIFEST = ROOT / "data/geo/generated/manifest/validation_report.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    full_path = BASE / "areacity_full_level0-2.geojson"
    level_paths = [BASE / f"areacity_level{i}.geojson" for i in range(3)]

    full = load(full_path)
    checks = {
        "full_exists": full_path.exists(),
        "full_type": full.get("type") == "FeatureCollection",
        "full_feature_count": len(full.get("features", [])),
        "levels": {},
        "full_deep_values": sorted({f["properties"]["deep"] for f in full.get("features", [])}),
    }

    for level, path in enumerate(level_paths):
        data = load(path)
        features = data.get("features", [])
        checks["levels"][str(level)] = {
            "exists": path.exists(),
            "type_ok": data.get("type") == "FeatureCollection",
            "feature_count": len(features),
            "all_match_deep": all(f["properties"]["deep"] == level for f in features),
            "all_have_geometry": all(f.get("geometry") is not None for f in features),
        }

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
