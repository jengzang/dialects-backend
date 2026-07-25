from inspect import signature

from app.routes.vocabulary import get_vocabulary_items, upload_vocabulary
from app.service.auth.core.dependencies import get_current_user


def test_upload_endpoint_depends_on_current_user() -> None:
    dependency = signature(upload_vocabulary).parameters["current_user"].default.dependency
    assert dependency is get_current_user


def test_main_routes_registers_vocabulary_upload_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/upload" in paths


def test_main_routes_registers_vocabulary_items_endpoint() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/items" in paths


def test_items_endpoint_accepts_query_parameters() -> None:
    parameters = signature(get_vocabulary_items).parameters

    assert "q" in parameters
    assert "search_fields" in parameters
    assert "locations" in parameters
    assert "page" in parameters
    assert "page_size" in parameters


def test_main_routes_registers_vocabulary_sql_endpoints() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", None)
    }
    assert "/api/vocabulary/sql/query" in paths
    assert "/api/vocabulary/sql/mutate" in paths
    assert "/api/vocabulary/sql/batch-replace-execute" in paths
