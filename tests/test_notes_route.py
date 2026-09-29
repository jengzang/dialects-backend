from fastapi.testclient import TestClient

from app.common.api_config import RECORD_API
from app.service.logging.utils.route_matcher import match_route_config


def test_main_app_registers_the_public_notes_route():
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }

    assert "/api/notes" in paths
    assert "/api/vocabulary/notes" not in paths
    assert "/api/notes" in app.openapi()["paths"]


def test_notes_route_forwards_repeated_scope_parameters_with_pagination(monkeypatch):
    from app.main import app
    from app.routes import notes as notes_routes
    from app.sql.db_selector import get_dialects_db, get_query_db

    captured = {}

    def fake_query_notes(**kwargs):
        captured.update(kwargs)
        return {
            "items": [
                {
                    "id": 1,
                    "location_name": "甲地",
                    "character": "字",
                    "ipa": "pa",
                    "notes": "注",
                }
            ],
            "total": 1,
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
        }

    monkeypatch.setattr(notes_routes, "query_notes", fake_query_notes)
    app.dependency_overrides[get_dialects_db] = lambda: "dialects.db"
    app.dependency_overrides[get_query_db] = lambda: "query.db"
    try:
        response = TestClient(app).get(
            "/api/notes",
            params=[
                ("q", "文白"),
                ("search_fields", "detail"),
                ("search_fields", "pronunciation"),
                ("locations", "甲地"),
                ("locations", "乙地"),
                ("regions", "閩"),
                ("regions", "閩南"),
                ("region_mode", "yindian"),
                ("page", "2"),
                ("page_size", "50"),
            ],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "location_name": "甲地",
                "character": "字",
                "ipa": "pa",
                "notes": "注",
            }
        ],
        "total": 1,
        "page": 2,
        "page_size": 50,
    }
    assert captured == {
        "q": "文白",
        "search_fields": ["detail", "pronunciation"],
        "locations": ["甲地", "乙地"],
        "regions": ["閩", "閩南"],
        "region_mode": "yindian",
        "page": 2,
        "page_size": 50,
        "notes_db_path": "dialects.db",
        "query_db_path": "query.db",
    }


def test_notes_route_uses_pagination_defaults_and_allows_a_missing_keyword(monkeypatch):
    from app.main import app
    from app.routes import notes as notes_routes
    from app.sql.db_selector import get_dialects_db, get_query_db

    def fake_query_notes(**kwargs):
        return {
            "items": [],
            "total": 0,
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
        }

    monkeypatch.setattr(notes_routes, "query_notes", fake_query_notes)
    app.dependency_overrides[get_dialects_db] = lambda: "dialects.db"
    app.dependency_overrides[get_query_db] = lambda: "query.db"
    try:
        client = TestClient(app)
        default_response = client.get("/api/notes", params={"q": "文"})
        blank_response = client.get("/api/notes")
        invalid_mode_response = client.get(
            "/api/notes",
            params={"q": "文", "region_mode": "unknown"},
        )
    finally:
        app.dependency_overrides.clear()

    assert default_response.status_code == 200
    assert default_response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 50,
    }
    assert blank_response.status_code == 200
    assert blank_response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 50,
    }
    assert invalid_mode_response.status_code == 400


def test_notes_response_models_expose_the_card_payload_shape():
    from app.schemas.notes import NotesItemResponse, NotesSearchResponse

    response = NotesSearchResponse(
        items=[
            NotesItemResponse(
                id=1,
                location_name="甲地",
                character="字",
                ipa="pa",
                notes="注",
            )
        ],
        total=1,
        page=1,
        page_size=50,
    )

    assert response.model_dump() == {
        "items": [
            {
                "id": 1,
                "location_name": "甲地",
                "character": "字",
                "ipa": "pa",
                "notes": "注",
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 50,
    }


def test_notes_route_has_an_exact_public_rate_limited_policy_and_usage_recording():
    config = match_route_config("/api/notes")

    assert config == {
        "rate_limit": True,
        "require_login": False,
        "log_params": True,
        "log_body": False,
    }
    assert "/api/notes" in RECORD_API
