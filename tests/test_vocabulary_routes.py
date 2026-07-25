from inspect import signature

from app.routes.vocabulary import upload_vocabulary
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
