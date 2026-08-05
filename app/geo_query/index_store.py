from __future__ import annotations

import json
import sqlite3
from typing import Sequence

from .models import FeatureRecord, SubGeometryIndexRecord


# --- meta ---

def load_meta(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT key, value FROM meta").fetchall()
    return {row["key"]: json.loads(row["value"]) for row in rows}


# --- features ---

def _row_to_feature(row: sqlite3.Row) -> FeatureRecord:
    return FeatureRecord(
        id=int(row["id"]),
        pid=int(row["pid"]),
        deep=int(row["deep"]),
        name=str(row["name"]),
        ext_path=str(row["ext_path"]),
        center_lng=float(row["center_lng"]) if row["center_lng"] is not None else None,
        center_lat=float(row["center_lat"]) if row["center_lat"] is not None else None,
        source_crs=str(row["source_crs"]),
        target_crs=str(row["target_crs"]),
        source_file=str(row["source_file"]),
        geometry_type=str(row["geometry_type"]) if row["geometry_type"] is not None else None,
        geometry_exists=bool(row["geometry_exists"]),
    )


def load_feature_by_id(conn: sqlite3.Connection, feature_id: int) -> FeatureRecord | None:
    row = conn.execute("SELECT * FROM features WHERE id = ?", (int(feature_id),)).fetchone()
    return _row_to_feature(row) if row else None


def search_features(conn: sqlite3.Connection, q: str, deep: int | None) -> list[FeatureRecord]:
    q = f"%{q.strip().lower()}%"
    if deep is not None:
        rows = conn.execute(
            "SELECT * FROM features WHERE deep = ? AND (LOWER(name) LIKE ? OR LOWER(ext_path) LIKE ?)",
            (deep, q, q),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM features WHERE LOWER(name) LIKE ? OR LOWER(ext_path) LIKE ?",
            (q, q),
        ).fetchall()
    return [_row_to_feature(row) for row in rows]


def query_children(conn: sqlite3.Connection, parent_id: int | None, deep: int | None) -> list[FeatureRecord]:
    conditions = []
    params: list = []
    if parent_id is not None:
        conditions.append("pid = ?")
        params.append(int(parent_id))
    if deep is not None:
        conditions.append("deep = ?")
        params.append(int(deep))
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(
        f"SELECT * FROM features WHERE {where} ORDER BY deep, id",
        tuple(params),
    ).fetchall()
    return [_row_to_feature(row) for row in rows]


def load_all_features(conn: sqlite3.Connection) -> dict[int, FeatureRecord]:
    rows = conn.execute("SELECT * FROM features").fetchall()
    return {int(row["id"]): _row_to_feature(row) for row in rows}


# --- subgeometries ---

def count_subgeometries(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM subgeometries").fetchone()
    return int(row["c"] if row else 0)


def _row_to_subgeom_record(row: sqlite3.Row) -> SubGeometryIndexRecord:
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
    )


def load_geometry_blob(conn: sqlite3.Connection, sub_id: int) -> bytes | None:
    row = conn.execute("SELECT geom_blob FROM subgeometries WHERE sub_id = ?", (int(sub_id),)).fetchone()
    return bytes(row["geom_blob"]) if row else None


def load_subgeometry_by_ids(conn: sqlite3.Connection, sub_ids: Sequence[int]) -> list[SubGeometryIndexRecord]:
    if not sub_ids:
        return []
    placeholders = ",".join("?" for _ in sub_ids)
    query = f"""
        SELECT sub_id, feature_id, deep, part_index, part_kind, source_geometry_type,
               min_lng, min_lat, max_lng, max_lat
        FROM subgeometries
        WHERE sub_id IN ({placeholders})
    """
    row_map = {
        int(row["sub_id"]): _row_to_subgeom_record(row)
        for row in conn.execute(query, tuple(int(v) for v in sub_ids)).fetchall()
    }
    return [row_map[sub_id] for sub_id in sub_ids if sub_id in row_map]


def query_candidate_records_by_bbox(conn: sqlite3.Connection, bbox: tuple[float, float, float, float]) -> list[SubGeometryIndexRecord]:
    min_lng, min_lat, max_lng, max_lat = bbox
    rows = conn.execute(
        """
        SELECT s.sub_id, s.feature_id, s.deep, s.part_index, s.part_kind, s.source_geometry_type,
               s.min_lng, s.min_lat, s.max_lng, s.max_lat
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
    return [_row_to_subgeom_record(row) for row in rows]


def query_feature_part_ids(conn: sqlite3.Connection, feature_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT sub_id FROM feature_parts WHERE feature_id = ? ORDER BY part_index, sub_id",
        (int(feature_id),),
    ).fetchall()
    return [int(row["sub_id"]) for row in rows]
