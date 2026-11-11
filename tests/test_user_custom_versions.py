import pytest
from fastapi import HTTPException

from app.service.user.core.models import Information
from tests.test_user_custom_mutations import factory, USER, update_item


def test_orm_legacy_and_admin_writes_increment_version(factory):
    from app.schemas.user.custom_mutations import BatchUpdateRequest
    from app.service.user.submission.mutations import batch_update
    with factory() as db:
        row=db.get(Information,1)
        row.存儲標記=0
        db.commit()
        assert row.version==2
    with pytest.raises(HTTPException) as error:
        batch_update(USER,BatchUpdateRequest(items=[update_item(值='66'),update_item(2,值='77')]),factory)
    assert error.value.detail['code']=='version_conflict'
    with factory() as db:
        assert db.get(Information,2).值=='55'


def test_two_clients_stale_update_and_delete_rejected(factory):
    from app.schemas.user.custom_mutations import BatchUpdateRequest, BatchDeleteByIdRequest
    from app.service.user.submission.mutations import batch_update, batch_delete_by_id
    batch_update(USER,BatchUpdateRequest(items=[update_item(值='66')]),factory)
    for operation,req in [
        (batch_update,BatchUpdateRequest(items=[update_item(值='77')])),
        (batch_delete_by_id,BatchDeleteByIdRequest(items=[dict(id=1,version=1)])),
    ]:
        with pytest.raises(HTTPException) as error:
            operation(USER,req,factory)
        assert error.value.detail['code']=='version_conflict'
    with factory() as db:
        assert db.get(Information,1).值=='66'


def test_missing_schema_returns_migration_required(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.schemas.user.custom_mutations import BatchUpdateRequest
    from app.service.user.submission.mutations import batch_update
    engine=create_engine(f'sqlite:///{tmp_path / "old.db"}')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE informations (id INTEGER PRIMARY KEY, user_id INTEGER)')
    try:
        with pytest.raises(HTTPException) as error:
            batch_update(USER,BatchUpdateRequest(items=[update_item()]),sessionmaker(bind=engine))
        assert error.value.status_code==503
        assert error.value.detail['code']=='migration_required'
    finally:
        engine.dispose()


def test_migration_is_explicit_idempotent_and_keeps_historical_rows(tmp_path):
    import sqlite3
    from scripts.migrate_user_custom_safety import inspect_schema, migrate
    path=tmp_path/'old.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE informations (id INTEGER PRIMARY KEY, user_id INTEGER)')
        conn.execute('INSERT INTO informations VALUES (1,1)')
    assert not inspect_schema(path)['ready']
    assert migrate(path)['ready']
    assert migrate(path)['ready']
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT id,version FROM informations').fetchone()==(1,1)


def test_highest_deleted_id_is_never_reused(factory):
    from app.schemas.user.custom_mutations import BatchUpdateRequest
    from app.service.user.submission.mutations import batch_update
    from tests.test_user_custom_mutations import FIELDS
    with factory() as db:
        row=db.get(Information,3)
        row.user_id=1
        db.commit()
        db.delete(row)
        db.commit()
        new=Information(**FIELDS,user_id=1,username='tester',maxValue='55')
        db.add(new)
        db.commit()
        assert new.id > 3
    with pytest.raises(HTTPException) as error:
        batch_update(USER,BatchUpdateRequest(items=[update_item(3,值='66')]),factory)
    assert error.value.status_code==404


def test_migration_preserves_unknown_columns_indexes_and_ids(tmp_path):
    import sqlite3
    from scripts.migrate_user_custom_safety import inspect_schema,migrate
    path=tmp_path/'legacy.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE informations (id INTEGER NOT NULL, user_id INTEGER, future_field TEXT DEFAULT "x", PRIMARY KEY (id))')
        db.execute('CREATE INDEX custom_future_index ON informations(future_field)')
        db.execute('INSERT INTO informations(id,user_id,future_field) VALUES (9,1,"preserved")')
    assert not inspect_schema(path)['ready']
    assert migrate(path)['ready']
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT id,future_field,version FROM informations').fetchone()==(9,'preserved',1)
        assert 'custom_future_index' in {row[1] for row in db.execute('PRAGMA index_list(informations)')}
        db.execute('DELETE FROM informations WHERE id=9')
        db.execute('INSERT INTO informations(user_id) VALUES (1)')
        assert db.execute('SELECT id FROM informations').fetchone()[0] > 9


def test_migration_foreign_reference_aborts_without_changes(tmp_path):
    import sqlite3
    from scripts.migrate_user_custom_safety import migrate
    path=tmp_path/'foreign.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE informations (id INTEGER PRIMARY KEY, user_id INTEGER)')
        db.execute('CREATE TABLE dependents (id INTEGER, info_id INTEGER REFERENCES informations(id))')
    with pytest.raises(ValueError,match='foreign'):
        migrate(path)
    with sqlite3.connect(path) as db:
        assert 'version' not in {row[1] for row in db.execute('PRAGMA table_info(informations)')}
