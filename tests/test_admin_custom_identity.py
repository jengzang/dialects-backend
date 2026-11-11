from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.user.core.models import Base, Information
from app.service.admin.submissions import management
from app.schemas.admin.submissions import InformationBase


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def record(value, micros):
    return Information(user_id=7, username='alice', 簡稱='a', 音典分區='b', 經緯度='c', 聲韻調='', 特徵='d', 值=value, 說明='', maxValue='1', created_at=datetime(2026, 1, 1, 0, 0, 0, micros))


class Users:
    def query(self, *args): return self
    def filter(self, *args): return self
    def first(self): return SimpleNamespace(id=7, username='alice', role='user')


def test_response_exposes_distinct_ids(db):
    a, b = record('1', 100000), record('2', 150000)
    db.add_all([a, b]); db.commit()
    assert InformationBase.model_validate(a).id != InformationBase.model_validate(b).id


def test_update_is_atomic_and_preserves_created_at(db):
    a, b = record('1', 100000), record('2', 150000)
    db.add_all([a, b]); db.commit()
    before = a.created_at
    payload = dict(id=a.id, username='alice', 簡稱='a', 音典分區='b', 經緯度='c', 聲韻調='', 特徵='d', 值='3', 說明='')
    result = management.update_custom_by_admin(db, Users(), [payload, {**payload, 'id': 999}], SimpleNamespace(username='admin'))
    assert not result['success']
    db.expire_all()
    assert db.get(Information, a.id).值 == '1'
    assert a.created_at == before
    result = management.update_custom_by_admin(db, Users(), [payload], SimpleNamespace(username='admin'))
    assert result['success'] and a.值 == '3' and a.created_at == before
    assert b.值 == '2'


def test_delete_by_id_does_not_delete_neighbor_and_rejects_invalid_batch(db):
    a, b = record('1', 100000), record('2', 150000)
    db.add_all([a, b]); db.commit()
    admin = SimpleNamespace(username='admin')
    result = management.delete_custom_ids(db, Users(), [{'id': a.id, 'username': 'alice'}, {'id': 999, 'username': 'alice'}], admin)
    assert not result['success'] and db.get(Information, a.id) is not None
    result = management.delete_custom_ids(db, Users(), [{'id': a.id, 'username': 'alice'}], admin)
    assert result['success'] and db.get(Information, a.id) is None and db.get(Information, b.id) is not None


def test_update_refuses_other_admin(db):
    a = record('1', 100000)
    db.add(a); db.commit()
    class AdminUsers(Users):
        def first(self): return SimpleNamespace(id=7, username='alice', role='admin')
    payload = dict(id=a.id, username='alice', 簡稱='a', 音典分區='b', 經緯度='c', 聲韻調='', 特徵='d', 值='3', 說明='')
    result = management.update_custom_by_admin(db, AdminUsers(), [payload], SimpleNamespace(username='other'))
    assert not result['success'] and a.值 == '1'


def test_region_delete_uses_id_and_username(db, monkeypatch):
    from app.service.user.core.models import UserRegion
    from app.service.user.submission.region import delete_region_admin
    from app.service.auth.database import connection
    first = UserRegion(user_id=7, username='alice', region_name='first', locations='[]', created_at=datetime(2026, 1, 1, 0, 0, 0, 100000))
    other = UserRegion(user_id=8, username='bob', region_name='other', locations='[]', created_at=first.created_at)
    db.add_all([first, other]); db.commit()
    class UserSession(Users):
        def close(self): pass
    monkeypatch.setattr(connection, 'SessionLocal', UserSession)
    assert not delete_region_admin(db, 'alice', region_id=other.id)
    assert delete_region_admin(db, 'alice', region_id=first.id)
    assert db.get(UserRegion, other.id) is not None


def test_region_delete_requires_identity():
    from pydantic import ValidationError
    from app.schemas.admin.submissions import AdminRegionDelete
    with pytest.raises(ValidationError):
        AdminRegionDelete(username='alice')
    assert AdminRegionDelete(username='alice', id=1).id == 1
    assert AdminRegionDelete(username='alice', created_at='2026-01-01').created_at


def test_legacy_admin_delete_refuses_ambiguous_timestamp(db):
    a, b = record('1', 0), record('2', 0)
    db.add_all([a, b]); db.commit()
    result = management.delete_custom_by_admin(db, Users(), [{'username': 'alice', 'created_at': a.created_at}], SimpleNamespace(username='admin'))
    assert not result['success']
    db.expire_all()
    assert db.query(Information).count() == 2
