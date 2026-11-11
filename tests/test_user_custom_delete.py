"""Legacy deletion preserves optional phonology while rejecting ambiguity."""
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.user.core.models import Base, Information
from app.service.user.submission.delete import handle_form_deletion


@pytest.fixture
def deletion_db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        for phonology in ('調值', '漢字'):
            db.add(Information(user_id=7, username='tester', 簡稱='茶山增埗', 音典分區='嶺南', 經緯度='113,23', 聲韻調=phonology, 特徵='陰平', 值='55', maxValue='55', created_at=datetime(2026, 6, 1, 10)))
        db.commit()
    yield factory
    engine.dispose()


def test_delete_form_uses_optional_phonology_when_provided(deletion_db):
    with deletion_db() as db:
        result = handle_form_deletion(dict(location='茶山增埗', phonology='調值', feature='陰平', value='55', created_at='2026-06-01T10:00:00'), SimpleNamespace(id=7), db)
    assert result['success']
    with deletion_db() as db:
        assert [row.聲韻調 for row in db.query(Information).all()] == ['漢字']


def test_delete_form_without_phonology_refuses_ambiguous_matches(deletion_db):
    with deletion_db() as db:
        with pytest.raises(HTTPException) as caught:
            handle_form_deletion(dict(location='茶山增埗', feature='陰平', value='55', created_at='2026-06-01T10:00:00'), SimpleNamespace(id=7), db)
    assert caught.value.status_code == 409
    with deletion_db() as db:
        assert db.query(Information).count() == 2
