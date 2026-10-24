import asyncio
import io
import threading
from types import SimpleNamespace

import pytest
from starlette.datastructures import UploadFile


def test_preview_parsing_does_not_block_event_loop(monkeypatch):
    from app.routes import vocabulary
    entered, release = threading.Event(), threading.Event()
    def preview(**kwargs):
        entered.set()
        assert release.wait(2), 'event loop blocked while parsing'
        assert hasattr(kwargs['content'], 'read')
        return {'ok': True}
    monkeypatch.setattr(vocabulary, 'preview_vocabulary_upload', preview)
    db = SimpleNamespace(get_bind=lambda: SimpleNamespace(url=SimpleNamespace(database='test-preview.db')))
    async def scenario():
        task = asyncio.create_task(vocabulary.preview_vocabulary_upload_endpoint(
            file=UploadFile(io.BytesIO(b'data'), filename='words.csv'), location='{}',
            parser_mode='auto', fill_standard_from_local=False, target_user_id=None,
            current_user=None, db=db))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            release.set()
            assert await task == {'ok': True}
        finally:
            release.set()
    asyncio.run(scenario())


def test_expensive_work_is_serial_and_cancellation_retains_lease(monkeypatch, tmp_path):
    from app.service.vocabulary.resources import run_bounded
    monkeypatch.setenv('TOPONYMS_LOCK_DIR', str(tmp_path / 'locks'))
    entered, release = threading.Event(), threading.Event()
    events = []
    def first():
        entered.set()
        release.wait(3)
        events.append('commit')
    def second(): events.append('second')
    async def scenario():
        a = asyncio.create_task(run_bounded('test', first, expensive=True))
        assert await asyncio.to_thread(entered.wait, 2)
        a.cancel()
        b = asyncio.create_task(run_bounded('test', second, expensive=True))
        await asyncio.sleep(.05)
        assert not b.done()
        a.cancel()  # A second cancellation must not release a running SQLite worker.
        release.set()
        with pytest.raises(asyncio.CancelledError): await a
        await b
        assert events == ['commit', 'second']
    try: asyncio.run(scenario())
    finally: release.set()


def test_file_export_is_complete_and_removed_after_response(tmp_path):
    from pathlib import Path
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from openpyxl import load_workbook
    from app.routes.vocabulary import _build_location_export_response
    response = _build_location_export_response('地点', ((f'词{i}', '当地', 'a', '') for i in range(1200)))
    assert hasattr(response, 'path'), 'export must be backed by a file'
    path = Path(response.path)
    assert path.is_file()
    app = FastAPI()
    @app.get('/export')
    def export(): return response
    result = TestClient(app).get('/export')
    assert result.status_code == 200
    book = load_workbook(io.BytesIO(result.content), read_only=True)
    try:
        rows = list(book.active.values)
        assert len(rows) == 1201
        assert rows[-1][0] == '词1199'
    finally: book.close()
    assert not path.exists()


def test_export_construction_failure_removes_tempfile(monkeypatch, tmp_path):
    from app.routes import vocabulary
    from tempfile import mkstemp
    created = []
    def temporary(**kwargs):
        fd, path = mkstemp(dir=tmp_path)
        created.append(path)
        return fd, path
    monkeypatch.setattr(vocabulary, 'mkstemp', temporary)
    def fail(**kwargs): raise RuntimeError('workbook failed')
    monkeypatch.setattr(vocabulary, 'Workbook', fail)
    with pytest.raises(RuntimeError, match='workbook failed'):
        vocabulary._build_location_export_response('地点', [])
    from pathlib import Path
    assert created and all(not Path(p).exists() for p in created)


def test_export_send_failure_removes_tempfile():
    from pathlib import Path
    from app.routes.vocabulary import _build_location_export_response
    response = _build_location_export_response('地点', [('词', '词', 'a', '')])
    async def scenario():
        async def send(message): raise OSError('client disconnected')
        async def receive(): return {'type': 'http.disconnect'}
        with pytest.raises(OSError):
            await response({'type': 'http', 'method': 'GET', 'headers': []}, receive, send)
    asyncio.run(scenario())
    assert not Path(response.path).exists()
