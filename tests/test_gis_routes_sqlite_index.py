from fastapi.testclient import TestClient

from app.main import create_gis_app


def test_gis_routes_status_search_children_boundary_and_point():
    app = create_gis_app()
    client = TestClient(app)

    status_resp = client.get("/api/gis/status")
    assert status_resp.status_code == 200
    status = status_resp.json()
    assert status["loaded"] is True
    assert status["feature_count"] > 0
    assert status["subgeometry_count"] > 0
    assert status["index_path"].endswith("gis.db")

    point_resp = client.get("/api/gis/query/point", params={"lng": 116.4074, "lat": 39.9042})
    assert point_resp.status_code == 200
    point_data = point_resp.json()
    assert point_data["stats"]["exact_hit_count"] >= 1
    assert any(item["name"] == "北京市" for item in point_data["result"])

    tolerance_resp = client.get(
        "/api/gis/query/point-with-tolerance",
        params={"lng": 116.4074, "lat": 39.9042, "tolerance_metre": 5000},
    )
    assert tolerance_resp.status_code == 200
    tolerance_data = tolerance_resp.json()
    assert tolerance_data["stats"]["exact_hit_count"] >= 1

    search_resp = client.get("/api/gis/search", params={"q": "北京"})
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["success"] is True
    assert any(item["name"] == "北京市" for item in search_data["items"])

    children_resp = client.get("/api/gis/children", params={"deep": 0})
    assert children_resp.status_code == 200
    children_data = children_resp.json()
    assert children_data["success"] is True
    assert any(item["name"] == "北京市" for item in children_data["items"])

    boundary_resp = client.get("/api/gis/boundary/by-id", params={"feature_id": 110101})
    assert boundary_resp.status_code == 200
    boundary_data = boundary_resp.json()
    assert boundary_data["feature"]["id"] == 110101
    assert boundary_data["geometry"]["type"] in {"Polygon", "MultiPolygon"}


def test_gis_resolve_returns_unique_feature_with_structured_path():
    app = create_gis_app()
    client = TestClient(app)

    resp = client.get(
        "/api/gis/resolve",
        params={"province": "北京市", "city": "北京市", "county": "东城区"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["matched"] is True
    assert data["ambiguous"] is False
    assert data["candidates"] == []
    assert data["feature"]["id"] == 110101
    assert data["feature"]["name"] == "东城区"
    assert data["feature"]["path"] == [
        {"id": 11, "name": "北京市", "deep": 0},
        {"id": 1101, "name": "北京市", "deep": 1},
        {"id": 110101, "name": "东城区", "deep": 2},
    ]
    assert data["feature"]["path_names"] == {
        "province": "北京市",
        "city": "北京市",
        "county": "东城区",
    }


def test_gis_resolve_accepts_slash_path_and_municipality_short_path():
    app = create_gis_app()
    client = TestClient(app)

    short_resp = client.get("/api/gis/resolve", params={"path": "北京市/东城区"})
    full_resp = client.get("/api/gis/resolve", params={"path": "北京市/北京市/东城区"})

    assert short_resp.status_code == 200
    assert full_resp.status_code == 200
    assert short_resp.json()["matched"] is True
    assert full_resp.json()["matched"] is True
    assert short_resp.json()["feature"]["id"] == 110101
    assert full_resp.json()["feature"]["id"] == 110101


def test_gis_resolve_reports_ambiguous_candidates_instead_of_guessing():
    app = create_gis_app()
    client = TestClient(app)

    resp = client.get("/api/gis/resolve", params={"province": "北京市"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["matched"] is False
    assert data["ambiguous"] is True
    assert data["feature"] is None
    assert [item["id"] for item in data["candidates"]] == [11, 1101]


def test_gis_resolve_reports_not_found_for_missing_path():
    app = create_gis_app()
    client = TestClient(app)

    resp = client.get("/api/gis/resolve", params={"province": "北京市", "city": "不存在的城市"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["matched"] is False
    assert data["ambiguous"] is False
    assert data["feature"] is None
    assert data["candidates"] == []


def test_gis_geometry_query_returns_intersections():
    app = create_gis_app()
    client = TestClient(app)

    body = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [116.35, 39.86],
                [116.48, 39.86],
                [116.48, 39.96],
                [116.35, 39.96],
                [116.35, 39.86],
            ]],
        }
    }
    resp = client.post("/api/gis/query/geometry", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"]["exact_hit_count"] >= 1
    assert any(item["name"] in {"北京市", "东城区", "西城区"} for item in data["result"])
