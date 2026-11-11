import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient


def client_for_limit(limit):
    from app.routes.user.custom_mutation_limits import LimitedMutationRoute

    app = FastAPI()
    router = APIRouter(route_class=LimitedMutationRoute)

    @router.post('/save')
    def save(body: dict):
        return body

    app.include_router(router, prefix='/user/custom')
    return TestClient(app)


def test_body_limit_counts_actual_streamed_bytes(monkeypatch):
    from app.routes.user import custom_mutation_limits as limits
    monkeypatch.setattr(limits, 'MAX_MUTATION_BODY_BYTES', 32)
    client = client_for_limit(32)
    response = client.post('/user/custom/save', content=(part for part in [b'{"x":"', b'x' * 40, b'"}']))
    assert response.status_code == 413
    assert response.json()['detail']['code'] == 'request_too_large'


def test_valid_body_is_available_to_fastapi(monkeypatch):
    from app.routes.user import custom_mutation_limits as limits
    monkeypatch.setattr(limits, 'MAX_MUTATION_BODY_BYTES', 32)
    response = client_for_limit(32).post('/user/custom/save', json={'x': 1})
    assert response.status_code == 200
    assert response.json() == {'x': 1}
