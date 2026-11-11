from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.service.user.core.models import Base, Information

FIELDS = dict(簡稱='甲地', 音典分區='甲区', 經緯度='113.0,23.0', 聲韻調='', 特徵='阴平', 值='55', 說明='')
USER = SimpleNamespace(id=1, username='tester', role='user')

@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        for i in range(3):
            db.add(Information(**FIELDS, user_id=1 if i < 2 else 2, username='tester', maxValue='55', created_at=datetime(2026,1,1)))
        db.commit()
    yield factory
    engine.dispose()

def update_item(id=1, **changes):
    return dict(FIELDS, id=id, version=1, **changes)

def test_update_preserves_identity_and_recomputes_value(factory):
    from app.schemas.user.custom_mutations import BatchUpdateRequest
    from app.service.user.submission.mutations import batch_update
    result = batch_update(USER, BatchUpdateRequest(items=[update_item(值='66/33')]), factory)
    assert result['data'][0]['id'] == 1
    assert result['data'][0]['version'] == 2
    assert result['data'][0]['created_at_utc'].endswith('Z')
    with factory() as db:
        row = db.get(Information, 1)
        assert row.maxValue == '66'
        assert row.created_at == datetime(2026,1,1)
        assert row.存儲標記 == 1
        assert db.get(Information, 2).值 == '55'

@pytest.mark.parametrize('target', [3, 999])
def test_unavailable_target_rolls_back_whole_batch(factory, target):
    from app.schemas.user.custom_mutations import BatchUpdateRequest
    from app.service.user.submission.mutations import batch_update
    with pytest.raises(HTTPException) as error:
        batch_update(USER, BatchUpdateRequest(items=[update_item(值='66'), update_item(target)]), factory)
    assert error.value.status_code == 404
    with factory() as db:
        assert db.get(Information,1).值 == '55'

@pytest.mark.parametrize('items', [[], [update_item()] * 51, [update_item(),update_item()]])
def test_rejects_invalid_batches(items):
    from app.schemas.user.custom_mutations import BatchUpdateRequest
    with pytest.raises(ValidationError):
        BatchUpdateRequest(items=items)

@pytest.mark.parametrize('field,value', [('簡稱',' '),('經緯度','nan,23'),('經緯度','181,23'),('值','x'*4001),('user_id',3)])
def test_field_validation(field,value):
    from app.schemas.user.custom_mutations import BatchUpdateRequest
    row = update_item()
    row[field]=value
    with pytest.raises(ValidationError):
        BatchUpdateRequest(items=[row])


def test_chinese_coordinate_separator_matches_existing_frontend():
    from app.schemas.user.custom_mutations import BatchUpdateRequest
    result = BatchUpdateRequest(items=[update_item(經緯度='113.0，23.0')])
    assert result.items[0].經緯度 == '113.0,23.0'

def test_mid_flush_error_rolls_back(factory):
    from app.schemas.user.custom_mutations import BatchUpdateRequest
    from app.service.user.submission.mutations import batch_update
    def explode(*args):
        raise RuntimeError('injected')
    event.listen(Information,'after_update',explode)
    try:
        with pytest.raises(RuntimeError):
            batch_update(USER,BatchUpdateRequest(items=[update_item(值='66'),update_item(2,值='77')]),factory)
    finally:
        event.remove(Information,'after_update',explode)
    with factory() as db:
        assert [db.get(Information,i).值 for i in (1,2)] == ['55','55']

def test_delete_strict_and_versioned(factory):
    from app.schemas.user.custom_mutations import BatchDeleteByIdRequest
    from app.service.user.submission.mutations import batch_delete_by_id
    with pytest.raises(HTTPException):
        batch_delete_by_id(USER,BatchDeleteByIdRequest(ids=[1,999]),factory)
    with factory() as db:
        assert db.get(Information,1)
    result=batch_delete_by_id(USER,BatchDeleteByIdRequest(items=[{'id':1,'version':1}]),factory)
    assert result['deleted_ids']==[1]


def test_database_lock_is_reported_without_internal_sql(factory):
    import sqlite3
    from sqlalchemy.orm import sessionmaker
    from app.schemas.user.custom_mutations import BatchUpdateRequest
    from app.service.user.submission.mutations import batch_update
    path=factory.kw['bind'].url.database
    connection=sqlite3.connect(path)
    connection.execute('BEGIN IMMEDIATE')
    engine=create_engine(f'sqlite:///{path}',connect_args={'timeout':0.01})
    try:
        with pytest.raises(HTTPException) as error:
            batch_update(USER,BatchUpdateRequest(items=[update_item(值='66')]),sessionmaker(bind=engine))
        assert error.value.status_code==503
        assert error.value.detail['code']=='database_busy'
        assert 'SQL' not in error.value.detail['message']
    finally:
        connection.rollback()
        connection.close()
        engine.dispose()
