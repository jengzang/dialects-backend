import sqlite3
from pathlib import Path

from app.geo_query.engine import AreaCityQueryPy


ROOT = Path(__file__).resolve().parents[1]
SQLITE_INDEX = ROOT / "data/geo/generated/engine/wgs84/areacity.index.sqlite"


def test_engine_bbox_candidates_and_boundary_rebuild():
    engine = AreaCityQueryPy()
    engine.init_store_in_wkb_file()

    candidates = engine.grid_candidates_for_bbox((116.35, 39.86, 116.48, 39.96))
    assert candidates
    assert any(record.feature_id == 110101 for record in candidates)

    boundary = engine.read_boundary_by_id(110101)
    assert boundary is not None
    assert boundary["feature"]["id"] == 110101
    assert boundary["geometry"]["type"] in {"Polygon", "MultiPolygon"}


def test_engine_point_and_geometry_queries():
    engine = AreaCityQueryPy()
    engine.init_store_in_wkb_file()

    point = engine.query_point(116.4074, 39.9042)
    assert point.stats.exact_hit_count >= 1
    assert any(item["name"] == "北京市" for item in point.result)

    geom = {
        "type": "Polygon",
        "coordinates": [[
            [116.35, 39.86],
            [116.48, 39.86],
            [116.48, 39.96],
            [116.35, 39.96],
            [116.35, 39.86],
        ]],
    }
    result = engine.query_geometry(geom)
    assert result.stats.exact_hit_count >= 1
    assert any(item["name"] in {"北京市", "东城区", "西城区"} for item in result.result)


def test_sqlite_index_is_runtime_source_of_truth():
    assert SQLITE_INDEX.exists()
    conn = sqlite3.connect(SQLITE_INDEX)
    try:
        subgeometry_count = conn.execute("SELECT COUNT(*) FROM subgeometries").fetchone()[0]
        rtree_count = conn.execute("SELECT COUNT(*) FROM subgeometry_rtree").fetchone()[0]
        feature_parts_count = conn.execute("SELECT COUNT(*) FROM feature_parts").fetchone()[0]
    finally:
        conn.close()

    assert subgeometry_count > 0
    assert rtree_count == subgeometry_count
    assert feature_parts_count == subgeometry_count
