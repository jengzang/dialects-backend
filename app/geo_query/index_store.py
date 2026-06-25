from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import FeatureRecord, SubGeometryIndexRecord


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_features(path: Path) -> dict[int, FeatureRecord]:
    features: dict[int, FeatureRecord] = {}
    for item in iter_jsonl(path):
        record = FeatureRecord(**item)
        features[record.id] = record
    return features


def load_index(path: Path) -> dict:
    payload = load_json(path)
    records = [SubGeometryIndexRecord(**item) for item in payload["subgeometries"]]
    grid_index: dict[str, list[int]] = {
        key: [int(v) for v in value]
        for key, value in payload.get("grid_index", {}).items()
    }
    subgrid_index: dict[str, list[int]] = {
        key: [int(v) for v in value]
        for key, value in payload.get("subgrid_index", {}).items()
    }
    feature_parts: dict[int, list[int]] = {
        int(key): [int(v) for v in value]
        for key, value in payload.get("feature_parts", {}).items()
    }
    return {
        "records": records,
        "grid_index": grid_index,
        "subgrid_index": subgrid_index,
        "feature_parts": feature_parts,
    }
