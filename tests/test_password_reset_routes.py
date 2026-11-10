import os
os.environ.setdefault('_RUN_TYPE', 'WEB')
os.environ.setdefault('AUTO_MIGRATE', 'false')

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.routes.auth import router
from app.service.auth.database.connection import get_db
from app.service.auth.database.models import Base


def test_reset_route_returns_language_independent_codes(monkeypatch, tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'auth.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(router, prefix='/api/auth')
    def database():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = database
    client = TestClient(app)
    url = '/api/auth/password-reset/requests'
    body = {'email': 'missing@gmail.com', 'new_password': 'new-secret'}
    monkeypatch.delenv('PASSWORD_RESET_ENABLED', raising=False)
    for language in ['zh-CN', 'zh-Hant', 'en']:
        result = client.post(url, json=body, headers={'Accept-Language': language})
        assert result.status_code == 503
        assert result.json() == {'detail': {'code': 'password_reset_unavailable'}}
    monkeypatch.setenv('PASSWORD_RESET_ENABLED', 'true')
    monkeypatch.setenv('PASSWORD_RESET_IMAP_PASSWORD', 'not-a-real-secret')
    for _ in range(3):
        result = client.post(url, json=body)
        assert result.status_code == 202
        assert result.json()['recipient'] == '2639548777@qq.com'
    result = client.post(url, json=body)
    assert result.status_code == 429
    assert result.headers['Retry-After'] == '600'
    assert result.json() == {'detail': {'code': 'password_reset_rate_limited'}}
    result = client.post(url, json={**body, 'new_password': '密' * 25})
    assert result.status_code == 400
    assert result.json() == {'detail': {'code': 'password_reset_invalid_password'}}
    engine.dispose()
