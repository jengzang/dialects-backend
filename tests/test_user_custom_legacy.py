from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.user.core.models import Base, Information
from app.service.user.submission.submit import handle_form_submission
from app.service.user.submission.delete import handle_form_deletion


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
    engine.dispose()


def test_ordinary_user_legacy_submission_obeys_shared_quota(db, monkeypatch):
    from app.service.user.submission import mutations
    monkeypatch.setattr(mutations, 'HOURLY_RECORD_LIMIT', 1)
    db.add(Information(user_id=7, username='alice', 簡稱='甲', 音典分區='乙', 經緯度='113,23', 聲韻調='调值', 特徵='阴平', 值='55', maxValue='55', created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    db.commit()
    with pytest.raises(HTTPException) as caught:
        handle_form_submission(dict(location='甲', region='乙', coordinates='113,23', phonology='调值', feature='阴平', value='33'), SimpleNamespace(id=7, username='alice', role='user'), db)
    assert caught.value.status_code == 429
    assert db.query(Information).count() == 1


def test_legacy_form_delete_refuses_multiple_matching_rows(db):
    for _ in range(2):
        db.add(Information(user_id=7, username='alice', 簡稱='甲', 音典分區='乙', 經緯度='113,23', 聲韻調='调值', 特徵='阴平', 值='55', maxValue='55', created_at=datetime(2026, 1, 1)))
    db.commit()
    with pytest.raises(HTTPException) as caught:
        handle_form_deletion(dict(location='甲', feature='阴平', value='55', created_at='2026-01-01T00:00:00Z'), SimpleNamespace(id=7, username='alice'), db)
    assert caught.value.status_code == 409
    assert db.query(Information).count() == 2
