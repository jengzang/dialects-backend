from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

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


def connect_index_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def count_subgeometries(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM subgeometries").fetchone()
    return int(row["c"] if row else 0)


def _row_to_record(row: sqlite3.Row) -> SubGeometryIndexRecord:
    return SubGeometryIndexRecord(
        sub_id=int(row["sub_id"]),
        feature_id=int(row["feature_id"]),
        deep=int(row["deep"]),
        part_index=int(row["part_index"]),
        part_kind=str(row["part_kind"]),
        source_geometry_type=str(row["source_geometry_type"]),
        bbox=(
            float(row["min_lng"]),
            float(row["min_lat"]),
            float(row["max_lng"]),
            float(row["max_lat"]),
        ),
        geom_offset=int(row["geom_offset"]),
        geom_length=int(row["geom_length"]),
        subgrid_refs=[],
    )


def load_subgeometry_by_ids(conn: sqlite3.Connection, sub_ids: Sequence[int]) -> list[SubGeometryIndexRecord]:
    if not sub_ids:
        return []
    placeholders = ",".join("?" for _ in sub_ids)
    query = f"""
        SELECT sub_id, feature_id, deep, part_index, part_kind, source_geometry_type,
               min_lng, min_lat, max_lng, max_lat, geom_offset, geom_length
        FROM subgeometries
        WHERE sub_id IN ({placeholders})
    """
    row_map = {
        int(row["sub_id"]): _row_to_record(row)
        for row in conn.execute(query, tuple(int(v) for v in sub_ids)).fetchall()
    }
    return [row_map[sub_id] for sub_id in sub_ids if sub_id in row_map]


def query_candidate_records_by_bbox(conn: sqlite3.Connection, bbox: tuple[float, float, float, float]) -> list[SubGeometryIndexRecord]:
    min_lng, min_lat, max_lng, max_lat = bbox
    rows = conn.execute(
        """
        SELECT s.sub_id, s.feature_id, s.deep, s.part_index, s.part_kind, s.source_geometry_type,
               s.min_lng, s.min_lat, s.max_lng, s.max_lat, s.geom_offset, s.geom_length
        FROM subgeometry_rtree r
        JOIN subgeometries s ON s.sub_id = r.sub_id
        WHERE r.max_lng >= ?
          AND r.min_lng <= ?
          AND r.max_lat >= ?
          AND r.min_lat <= ?
        ORDER BY s.sub_id
        """,
        (min_lng, max_lng, min_lat, max_lat),
    ).fetchall()
    return [_row_to_record(row) for row in rows]


def query_feature_part_ids(conn: sqlite3.Connection, feature_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT sub_id FROM feature_parts WHERE feature_id = ? ORDER BY part_index, sub_id",
        (int(feature_id),),
    ).fetchall()
    return [int(row["sub_id"]) for row in rows]
