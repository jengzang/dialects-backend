from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import create_app


def dump_response(resp):
    print(resp.status_code)
    print(resp.text[:900])
    print("---")


def main() -> None:
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    status_resp = client.get("/api/gis/status")
    print("/api/gis/status")
    dump_response(status_resp)
    status_json = status_resp.json()
    assert status_json["split_mode"] == "polygon-parts-gridrefs-v1", status_json
    assert status_json["subgeometry_count"] > status_json["feature_count"], status_json
    assert status_json["features_with_multiple_parts"] > 0, status_json
    assert status_json["cache_max_items"] > 0, status_json
    assert status_json["subgrid_factor"] > status_json["grid_factor"], status_json

    point_resp = client.get("/api/gis/query/point?lng=121.550357&lat=29.874556")
    print("/api/gis/query/point?lng=121.550357&lat=29.874556")
    dump_response(point_resp)
    point_json = point_resp.json()
    assert point_json["stats"]["cache_hit_count"] >= 0, point_json
    assert point_json["stats"]["cache_miss_count"] >= 0, point_json
    assert point_json["result"], point_json

    paths = [
        "/api/gis/search?q=%E6%B5%99%E6%B1%9F",
        "/api/gis/children?deep=0",
        "/api/gis/boundary/by-id?feature_id=33",
        "/api/gis/query/point-with-tolerance?lng=121.993491&lat=29.524288&tolerance_metre=2500",
        "/api/gis/query/point?lng=999&lat=39.9",
    ]
    for path in paths:
        print(path)
        dump_response(client.get(path))

    boundary_resp = client.get("/api/gis/boundary/by-id?feature_id=33")
    boundary_json = boundary_resp.json()
    assert boundary_json["geometry"]["type"] == "MultiPolygon", boundary_json

    geom_payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[120.8, 29.0], [122.2, 29.0], [122.2, 30.4], [120.8, 30.4], [120.8, 29.0]]],
        }
    }
    print("/api/gis/query/geometry")
    dump_response(client.post("/api/gis/query/geometry", json=geom_payload))

    invalid_geom_payload = {"geometry": {"type": "Point", "coordinates": [116.3, 39.8]}}
    print("/api/gis/query/geometry invalid")
    dump_response(client.post("/api/gis/query/geometry", json=invalid_geom_payload))


if __name__ == "__main__":
    main()
