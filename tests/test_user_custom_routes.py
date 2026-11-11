from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.routes.user import custom_data
from app.service.user.core.models import Base, Information


@pytest.fixture
def api(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(custom_data, 'SessionLocal_info', factory)
    user = SimpleNamespace(id=7, username='alice', role='user')
    app = FastAPI()
    app.include_router(custom_data.router, prefix='/user/custom')
    app.dependency_overrides[custom_data.get_current_user] = lambda: user
    with factory() as db:
        a, b = [Information(user_id=7, username='alice', 簡稱='甲', 音典分區='乙', 經緯度='113,23', 聲韻調='', 特徵='阴平', 值=value, 說明='', maxValue=value, created_at=datetime(2026, 11, 9)) for value in ('55', '33')]
        db.add_all([a, b])
        db.commit()
        ids = [a.id, b.id]
    yield TestClient(app), factory, ids
    engine.dispose()


def edit_item(record_id):
    return dict(id=record_id, version=1, 簡稱='甲', 音典分區='乙', 經緯度='113,23', 聲韻調='', 特徵='阴平', 值='44', 說明='')


def test_id_update_and_strict_delete_are_exposed(api):
    client, factory, ids = api
    response = client.put('/user/custom/batch-update', json={'items': [edit_item(ids[0])]})
    assert response.status_code == 200, response.text
    assert response.json()['data'][0]['version'] == 2
    response = client.request('DELETE', '/user/custom/batch-delete-by-id', json={'items': [{'id': ids[1], 'version': 1}, {'id': 999, 'version': 1}]})
    assert response.status_code == 404
    with factory() as db:
        assert db.get(Information, ids[1]) is not None


def test_legacy_edit_rejects_ambiguous_timestamp(api):
    client, factory, ids = api
    response = client.put('/user/custom/edit', json={'created_at': '2026-11-09T00:00:00Z', '值': '99'})
    assert response.status_code == 409
    with factory() as db:
        assert db.get(Information, ids[0]).值 == '55'


def test_legacy_delete_rejects_missing_and_ambiguous_targets(api):
    client, factory, ids = api
    for dates, expected in [(['2026-11-09T00:00:00Z'], 409), (['2027-01-01T00:00:00Z'], 404)]:
        response = client.request('DELETE', '/user/custom/batch-delete', json={'created_at_list': dates})
        assert response.status_code == expected
    with factory() as db:
        assert db.query(Information).count() == 2


def test_save_and_replay_have_one_create(api):
    client, factory, ids = api
    item = edit_item(ids[0])
    item.pop('id')
    item.pop('version')
    item['client_row_id'] = 'new-1'
    payload = {'request_id': '52cdbd8c-2790-4b1f-b96f-3e0d6da9797c', 'creates': [item], 'updates': [], 'deletes': []}
    first = client.post('/user/custom/save', json=payload)
    second = client.post('/user/custom/save', json=payload)
    assert first.status_code == 200, first.text
    assert second.json() == first.json()
    with factory() as db:
        assert db.query(Information).count() == 3


def test_validation_response_preserves_row_location(api):
    client, _, ids = api
    invalid = edit_item(ids[0])
    invalid['值'] = ' '
    response = client.put('/user/custom/batch-update', json={'items': [invalid]})
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'validation_error'
    assert response.json()['detail']['errors'][0]['row_index'] == 0
