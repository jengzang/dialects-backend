import asyncio
import inspect
import sqlite3
import threading

import pytest
from fastapi import HTTPException

from app.routes import vocabulary_sql as routes
from app.schemas.vocabulary_sql import BatchReplaceExecuteParams
from app.service.vocabulary.database import create_vocabulary_engine_and_session
from app.service.vocabulary.models import Base, VocabularyEntry, VocabularyLog


class Admin:
    id = 1
    role = 'admin'


@pytest.fixture
def session(tmp_path, monkeypatch):
    engine, factory = create_vocabulary_engine_and_session(tmp_path / 'vocabulary.db')
    Base.metadata.create_all(engine)
    db = factory()
    monkeypatch.setattr(routes, 'notify_vocabulary_change', lambda *a, **kw: None)
    monkeypatch.setattr(routes, '_load_columns', lambda *a: {c.name for c in VocabularyEntry.__table__.columns})
    yield db
    db.close()
    engine.dispose()


def seed(db, count=1):
    db.bulk_insert_mappings(VocabularyEntry, [dict(user_id=1, location_name='test', standard_word='old', ipa='a', local_expression='', notes='x' * 4096) for _ in range(count)])
    db.commit()


def params(**kwargs):
    return BatchReplaceExecuteParams(table_name='vocabulary_entries', columns=['standard_word'], find_text='old', replace_text=kwargs.get('replace_text', 'new'), match_mode='exact')


def test_replace_validation_runs_off_event_loop(session, monkeypatch):
    seed(session)
    main_thread = threading.get_ident()
    original = routes._validate_entry_fields
    seen = []
    def validate(*args, **kwargs):
        seen.append(threading.get_ident())
        return original(*args, **kwargs)
    monkeypatch.setattr(routes, '_validate_entry_fields', validate)
    asyncio.run(routes.batch_replace_execute(params(), current_user=Admin(), db=session))
    assert seen and all(thread != main_thread for thread in seen)


def test_invalid_replace_rolls_back_transaction(session):
    seed(session)
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.batch_replace_execute(params(replace_text=''), current_user=Admin(), db=session))
    assert error.value.status_code == 400
    assert not session.connection().connection.in_transaction
    assert session.query(VocabularyEntry).one().standard_word == 'old'
    assert session.query(VocabularyLog).count() == 0


def test_large_replace_streams_narrow_rows_and_includes_last_row(session, monkeypatch):
    seed(session, 1025)
    original_connection = routes._connection
    batches = []
    projections = []
    class Cursor:
        def __init__(self, cursor):
            self.cursor = cursor
        def fetchmany(self, size):
            rows = self.cursor.fetchmany(size)
            batches.append((size, len(rows)))
            return rows
        def close(self):
            self.cursor.close()
        def fetchall(self):
            raise AssertionError('replacement must not materialize every row')
    class Connection:
        def __init__(self, connection):
            self.connection = connection
        @property
        def in_transaction(self):
            return self.connection.in_transaction
        def execute(self, sql, *args):
            cursor = self.connection.execute(sql, *args)
            if sql.startswith('SELECT ') and 'vocabulary_entries' in sql:
                projections.append(sql.split(' FROM ')[0])
                return Cursor(cursor)
            return cursor
    monkeypatch.setattr(routes, '_connection', lambda db: Connection(original_connection(db)))
    result = asyncio.run(routes.batch_replace_execute(params(), current_user=Admin(), db=session))
    assert result['affected_rows'] == 1025
    assert session.query(VocabularyEntry).filter(VocabularyEntry.standard_word == 'new').count() == 1025
    assert session.query(VocabularyEntry).order_by(VocabularyEntry.id.desc()).first().standard_word == 'new'
    assert batches == [(256, 256)] * 4 + [(256, 1), (256, 0)]
    assert projections == ['SELECT "standard_word"']
    assert session.query(VocabularyLog).one().affected_rows == 1025


def test_concurrent_change_during_validation_returns_conflict(session, monkeypatch):
    seed(session)
    original = routes._validate_entry_fields
    path = str(session.get_bind().url.database)
    def validate(*args, **kwargs):
        original(*args, **kwargs)
        with sqlite3.connect(path, timeout=0.1) as other:
            other.execute("UPDATE vocabulary_entries SET standard_word = 'concurrent'")
    monkeypatch.setattr(routes, '_validate_entry_fields', validate)
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.batch_replace_execute(params(), current_user=Admin(), db=session))
    assert error.value.status_code == 409
    assert not session.connection().connection.in_transaction
    assert session.query(VocabularyEntry).one().standard_word == 'concurrent'
    assert session.query(VocabularyLog).count() == 0


def test_sql_write_signatures_remain_async_and_preserve_dependencies():
    from app.service.auth.core.dependencies import get_current_user
    for endpoint in [routes.mutate_table, routes.batch_mutate_table, routes.batch_replace_preview, routes.batch_replace_execute]:
        assert inspect.iscoroutinefunction(endpoint)
        assert inspect.signature(endpoint).parameters['current_user'].default.dependency is get_current_user
        assert 'db' in inspect.signature(endpoint).parameters


@pytest.mark.parametrize('endpoint_name', ['mutate_table', 'batch_mutate_table', 'batch_replace_preview', 'batch_replace_execute'])
def test_sql_admission_and_validation_leave_event_loop_responsive(session, monkeypatch, endpoint_name):
    entered = threading.Event()
    released = threading.Event()
    def hold_validation(*args, **kwargs):
        entered.set()
        assert released.wait(1), 'event loop could not advance while SQL validation was running'
        raise HTTPException(status_code=403, detail='test stops before SQL mutation')
    monkeypatch.setattr(routes, '_require_table_access', hold_validation)
    async def exercise():
        task = asyncio.create_task(getattr(routes, endpoint_name)(params(), current_user=Admin(), db=session))
        try:
            for _ in range(100):
                if entered.is_set():
                    break
                await asyncio.sleep(0.005)
            assert entered.is_set()
            released.set()
            with pytest.raises(HTTPException) as error:
                await task
            assert error.value.status_code == 403
        finally:
            released.set()
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    asyncio.run(exercise())
