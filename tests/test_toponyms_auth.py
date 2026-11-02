import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ.setdefault("_RUN_TYPE", "WEB")
os.environ.setdefault("AUTO_MIGRATE", "false")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import setup_main_routes
from app.routes import toponyms
from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.connection import get_db
from app.service.logging.dependencies import limiter
from app.service.logging.utils.route_matcher import match_route_config


CASES = [
    ("points", {"q": "村", "limit": 1}, ([], False)),
    ("search", {"q": "村"}, ([], False)),
    ("names", {"q": "村"}, []),
    ("names", {"q": "村", "include_division_tree": True}, {"mode": "full", "items": []}),
    ("details", {"ids": "test-id"}, []),
    ("divisions", {}, []),
]


@pytest.mark.parametrize("endpoint,params,result", CASES)
def test_toponyms_require_login_before_query(monkeypatch, endpoint, params, result):
    app = FastAPI()
    setup_main_routes(app)
    execute = AsyncMock(return_value=result)
    usage = AsyncMock()
    monkeypatch.setattr(toponyms, "_execute", execute)
    monkeypatch.setattr(limiter, "check_api_usage_limit", usage)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: None

    path = f"/api/toponyms/{endpoint}"
    assert match_route_config(path)["require_login"] is True
    client = TestClient(app)
    response = client.get(path, params=params)
    assert response.status_code == 401
    execute.assert_not_awaited()
    usage.assert_not_awaited()

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="test-user", role="user")
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    execute.assert_awaited_once()
    usage.assert_awaited_once()
