import importlib
import json
import queue
import sqlite3
import threading
import time
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.service.auth.database.models import ApiUsageLog, ApiUsageSummary, Base, User


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    # Import-time table creation must not touch the application's databases.
    import app.common.path as paths

    with monkeypatch.context() as setup:
        setup.setattr(paths, "USER_DATABASE_URL", "sqlite:///:memory:")
        setup.setattr(paths, "LOGS_DATABASE_URL", "sqlite:///:memory:")
        module = importlib.import_module("app.service.logging.stats.auth_usage_pipeline")
        importlib.import_module("app.service.logging.core.workers")
    monkeypatch.setenv("AUTH_USAGE_RECOVERY_DIR", str(tmp_path / "recovery"))
    return module


@pytest.fixture
def queue_module(pipeline):
    return importlib.import_module("app.service.logging.core.queues")


@pytest.fixture
def auth_database(tmp_path, monkeypatch, pipeline):
    path = tmp_path / "auth.db"
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 0.01}
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        db.add(User(id=1, username="test", email="test@example.com", hashed_password="test"))
        db.commit()
    monkeypatch.setattr(pipeline, "AuthSessionLocal", factory)
    yield path, factory
    engine.dispose()


def api_log(**overrides):
    fields = dict(
        user_id=1, path="/api/notes", duration=0.5, status_code=200,
        called_at=datetime(2026, 10, 10, 1, 2, 3), request_size=1024, response_size=2048,
    )
    fields.update(overrides)
    return ApiUsageLog(**fields)


def summary_event(**overrides):
    fields = dict(user_id=1, path="/api/notes", duration=0.5, request_size=1024, response_size=2048)
    fields.update(overrides)
    return fields


def recovery_payloads(tmp_path):
    return [json.loads(path.read_text()) for path in (tmp_path / "recovery").glob("*.json")]


@pytest.mark.parametrize("stream", ["log", "summary"])
def test_real_sqlite_lock_is_retried_without_duplicate_writes(pipeline, auth_database, stream):
    path, factory = auth_database
    lock = sqlite3.connect(path, check_same_thread=False)
    lock.execute("BEGIN IMMEDIATE")
    release = threading.Timer(0.08, lock.rollback)
    release.start()
    try:
        if stream == "log":
            with factory() as db:
                result = pipeline.write_log_batch(db, [api_log()])
        else:
            result = pipeline.process_summary_batch([summary_event()])
        release.join()
        assert result is True
        with factory() as db:
            if stream == "log":
                assert db.query(ApiUsageLog).count() == 1
            else:
                row = db.query(ApiUsageSummary).one()
                assert row.count == 1
                assert float(row.total_upload) == 1.0
    finally:
        release.join()
        lock.close()


@pytest.mark.parametrize("stream", ["log", "summary"])
def test_permanent_failure_preserves_entire_batch(pipeline, auth_database, tmp_path, stream):
    _, factory = auth_database
    # One invalid foreign key must not silently discard the valid event beside it.
    if stream == "log":
        with factory() as db:
            result = pipeline.write_log_batch(db, [api_log(), api_log(user_id=999)])
    else:
        result = pipeline.process_summary_batch([summary_event(), summary_event(user_id=999)])
    saved = recovery_payloads(tmp_path)
    assert len(saved) == 1
    assert result is False
    assert saved[0]["queue_name"] == ("log_queue" if stream == "log" else "summary_queue")
    assert [item["user_id"] for item in saved[0]["events"]] == [1, 999]
    assert saved[0]["reason"] == "write_failed"
    with factory() as db:
        assert db.query(ApiUsageLog).count() == 0
        assert db.query(ApiUsageSummary).count() == 0


@pytest.mark.parametrize("stream", ["log", "summary"])
def test_full_auth_queue_preserves_event(queue_module, tmp_path, stream):
    q = queue.Queue(maxsize=1)
    q.put("occupied")
    item = api_log() if stream == "log" else summary_event()
    name = "log_queue" if stream == "log" else "summary_queue"
    assert queue_module.enqueue_with_backpressure(q, item, name) is False
    saved = recovery_payloads(tmp_path)
    assert len(saved) == 1
    assert saved[0]["reason"] == "queue_full"
    assert saved[0]["events"][0]["path"] == "/api/notes"
    if stream == "log":
        assert saved[0]["events"][0]["called_at"] == "2026-10-10T01:02:03"


@pytest.mark.parametrize("stream", ["log", "summary"])
def test_batches_flush_on_first_event_deadline_during_continuous_arrivals(
    pipeline, auth_database, monkeypatch, stream,
):
    q = queue.Queue()
    flushed = threading.Event()
    monkeypatch.setattr(pipeline, "AUTH_USAGE_BATCH_TIMEOUT_SECONDS", 0.05, raising=False)
    if stream == "log":
        monkeypatch.setattr(pipeline, "log_queue", q)
        monkeypatch.setattr(pipeline, "write_log_batch", lambda db, batch: flushed.set())
        target = pipeline.log_writer_thread
    else:
        monkeypatch.setattr(pipeline, "summary_queue", q)
        monkeypatch.setattr(pipeline, "process_summary_batch", lambda batch: flushed.set())
        target = pipeline.summary_writer
    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    try:
        # Never leave the queue idle long enough; stay below the size threshold.
        for _ in range(20):
            q.put(api_log() if stream == "log" else summary_event())
            time.sleep(0.01)
        assert flushed.is_set()
    finally:
        q.put(None)
        worker.join(2)
    assert not worker.is_alive()


def test_stop_waits_for_workers_to_flush_even_when_queue_is_full(pipeline, monkeypatch):
    workers = importlib.import_module("app.service.logging.core.workers")
    monkeypatch.setattr(workers, "_workers_started", False)
    monkeypatch.setattr(workers, "_worker_threads", [], raising=False)
    names = [
        ("keyword_log_queue", "keyword_log_writer"),
        ("diagnostic_queue", "diagnostic_event_writer"),
        ("statistics_queue", "statistics_writer"),
        ("html_visit_queue", "html_visit_writer"),
        ("log_queue", "log_writer_thread"),
        ("summary_queue", "summary_writer"),
        ("online_time_queue", "online_time_writer"),
    ]
    flushed = threading.Event()
    threads = []
    queues_by_name = {}
    for queue_name, target_name in names:
        q = queue.Queue(maxsize=1)
        queues_by_name[queue_name] = q
        monkeypatch.setattr(workers, queue_name, q)

        def consume(q=q, is_log=queue_name == "log_queue"):
            threads.append(threading.current_thread())
            if is_log:
                time.sleep(0.1)
            while q.get() is not None:
                pass
            if is_log:
                time.sleep(0.05)
                flushed.set()

        monkeypatch.setattr(workers, target_name, consume)
    workers.start_api_logger_workers()
    queues_by_name["log_queue"].put("last event")
    try:
        assert workers.stop_api_logger_workers() is True
        assert flushed.is_set()
        assert all(not worker.is_alive() for worker in threads)
    finally:
        for q in queues_by_name.values():
            try:
                q.put(None, timeout=0.2)
            except queue.Full:
                pass
        for thread in threads:
            thread.join(1)


def test_sqlite_busy_timeout_is_explicit_on_auth_connections(pipeline):
    connection = importlib.import_module("app.service.auth.database.connection")
    with connection.engine.connect() as db:
        assert db.exec_driver_sql("PRAGMA busy_timeout").scalar() == connection.SQLITE_BUSY_TIMEOUT_MS


@pytest.mark.parametrize("stream", ["log", "summary"])
def test_exhausted_lock_retries_preserve_events(pipeline, auth_database, tmp_path, caplog, stream):
    path, factory = auth_database
    lock = sqlite3.connect(path)
    lock.execute("BEGIN IMMEDIATE")
    try:
        if stream == "log":
            with factory() as db:
                assert pipeline.write_log_batch(db, [api_log()]) is False
        else:
            assert pipeline.process_summary_batch([summary_event()]) is False
    finally:
        lock.rollback()
        lock.close()
    assert len(recovery_payloads(tmp_path)) == 1
    assert sum("AUTH_USAGE_RETRY" in record.message for record in caplog.records) == 2


def test_retry_existing_summary_rolls_back_increment_before_retry(pipeline, auth_database):
    path, factory = auth_database
    with factory() as db:
        db.add(ApiUsageSummary(user_id=1, path="/api/notes", count=5, total_duration=2.5,
                               total_upload=5, total_download=10))
        db.commit()
    lock = sqlite3.connect(path, check_same_thread=False)
    lock.execute("BEGIN IMMEDIATE")
    release = threading.Timer(0.08, lock.rollback)
    release.start()
    try:
        assert pipeline.process_summary_batch([summary_event()]) is True
        with factory() as db:
            row = db.query(ApiUsageSummary).one()
            assert row.count == 6
            assert float(row.total_duration) == 3.0
            assert float(row.total_upload) == 6.0
            assert float(row.total_download) == 12.0
    finally:
        release.join()
        lock.close()


def test_worker_retains_batch_when_database_and_recovery_both_fail(
    pipeline, auth_database, monkeypatch, tmp_path,
):
    q = queue.Queue()
    saved = threading.Event()
    preserve = pipeline.preserve_auth_usage
    attempts = []

    def fail_once(queue_name, batch, **kwargs):
        attempts.append([item.user_id for item in batch])
        if len(attempts) == 1:
            raise OSError("recovery disk temporarily unavailable")
        result = preserve(queue_name, batch, **kwargs)
        saved.set()
        return result

    monkeypatch.setattr(pipeline, "preserve_auth_usage", fail_once)
    monkeypatch.setattr(pipeline, "log_queue", q)
    q.put(api_log())
    q.put(api_log(user_id=999))
    q.put(None)
    worker = threading.Thread(target=pipeline.log_writer_thread, daemon=True)
    worker.start()
    worker.join(3)
    assert not worker.is_alive()
    assert saved.is_set()
    assert attempts == [[1, 999], [1, 999]]
    assert len(recovery_payloads(tmp_path)) == 1


def test_overflow_with_unavailable_recovery_storage_reports_loss(queue_module, monkeypatch, caplog):
    def unavailable(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(queue_module, "preserve_auth_usage", unavailable)
    q = queue.Queue(maxsize=1)
    q.put("occupied")
    assert queue_module.enqueue_with_backpressure(q, api_log(), "log_queue") is False
    assert "AUTH_USAGE_LOST" in caplog.text


def test_recovery_files_are_private_and_fully_published(pipeline, tmp_path):
    from app.service.logging.core.auth_usage_recovery import preserve_auth_usage

    destination = preserve_auth_usage("log_queue", [api_log()], reason="write_failed")
    assert destination.stat().st_mode & 0o777 == 0o600
    assert not list((tmp_path / "recovery").glob("*.tmp"))
    assert json.loads(destination.read_text())["events"][0]["user_id"] == 1


def test_shutdown_timeout_does_not_duplicate_sentinel_or_start_consumers(pipeline, monkeypatch):
    workers = importlib.import_module("app.service.logging.core.workers")
    q = queue.Queue()
    signaled = threading.Event()
    release = threading.Event()

    def delayed_stop():
        assert q.get() is None
        signaled.set()
        release.wait(2)

    thread = threading.Thread(target=delayed_stop, daemon=True)
    monkeypatch.setattr(workers, "_worker_threads", [(q, thread)])
    monkeypatch.setattr(workers, "_stop_requested", set())
    monkeypatch.setattr(workers, "_workers_started", True)
    thread.start()
    try:
        assert workers.stop_api_logger_workers(timeout=0.02) is False
        assert signaled.is_set()
        assert workers._workers_started is True
        with pytest.raises(RuntimeError, match="shutdown"):
            workers.start_api_logger_workers()
        assert len(workers._worker_threads) == 1
        release.set()
        assert workers.stop_api_logger_workers(timeout=1) is True
        assert q.empty()
    finally:
        release.set()
        thread.join(2)


def test_published_recovery_file_is_not_retried_when_directory_sync_fails(
    pipeline, monkeypatch, tmp_path, caplog,
):
    recovery = importlib.import_module("app.service.logging.core.auth_usage_recovery")
    original_open = recovery.os.open

    def unavailable_directory_sync(path, flags, *args):
        if path == tmp_path / "recovery":
            raise OSError("directory sync unsupported")
        return original_open(path, flags, *args)

    monkeypatch.setattr(recovery.os, "open", unavailable_directory_sync)
    destination = recovery.preserve_auth_usage("log_queue", [api_log()], reason="write_failed")
    assert destination.exists()
    assert len(recovery_payloads(tmp_path)) == 1
    assert "AUTH_USAGE_RECOVERY_SYNC" in caplog.text


def test_closed_auth_queue_preserves_event(queue_module, tmp_path):
    class ClosedQueue:
        def put(self, *args, **kwargs):
            raise ValueError("Queue is closed")

    assert queue_module.enqueue_with_backpressure(ClosedQueue(), summary_event(), "summary_queue") is False
    saved = recovery_payloads(tmp_path)
    assert len(saved) == 1
    assert saved[0]["reason"] == "enqueue_failed"


def test_unconfirmed_rollback_only_retries_preservation_not_database(
    pipeline, monkeypatch, tmp_path,
):
    class UncertainSession:
        closed = False

        def commit(self):
            raise sqlite3.OperationalError("database is locked")

        def rollback(self):
            raise OSError("rollback unavailable")

        def close(self):
            self.closed = True

    db = UncertainSession()
    writes = []
    attempts = []
    preserve = pipeline.preserve_auth_usage

    def fail_once(*args, **kwargs):
        attempts.append(kwargs["reason"])
        if len(attempts) == 1:
            raise OSError("recovery storage unavailable")
        return preserve(*args, **kwargs)

    monkeypatch.setattr(pipeline, "preserve_auth_usage", fail_once)
    q = queue.Queue()
    q.put(summary_event())
    q.put(None)

    def write_batch(batch):
        return pipeline._write_auth_batch(db, batch, "summary_queue", lambda: writes.append("write"))

    worker = threading.Thread(target=pipeline._consume_auth_batches, args=(q, write_batch), daemon=True)
    worker.start()
    worker.join(3)
    assert not worker.is_alive()
    assert writes == ["write"]
    assert attempts == ["rollback_failed", "rollback_failed"]
    assert db.closed is True
    assert len(recovery_payloads(tmp_path)) == 1


@pytest.mark.parametrize("overflow", [False, True])
def test_http_usage_tracking_uses_shared_queue_and_recovery_logic(
    pipeline, auth_database, monkeypatch, tmp_path, overflow,
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.service.logging.middleware import traffic_logging

    _, factory = auth_database
    log_q = queue.Queue(maxsize=1)
    summary_q = queue.Queue(maxsize=1)
    if overflow:
        log_q.put("occupied")
        summary_q.put("occupied")
    monkeypatch.setattr(pipeline, "log_queue", log_q)
    monkeypatch.setattr(pipeline, "summary_queue", summary_q)
    monkeypatch.setattr(traffic_logging, "should_capture_diagnostic_path", lambda path: False)

    def get_db():
        with factory() as db:
            yield db

    async def get_user(request, db):
        return SimpleNamespace(id=1, role="user", username="test")

    monkeypatch.setattr(traffic_logging, "get_db", get_db)
    monkeypatch.setattr(traffic_logging, "get_current_user_for_middleware", get_user)
    app = FastAPI()
    app.add_middleware(traffic_logging.RequestLogMiddleware)

    @app.get("/api/notes")
    async def notes():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/api/notes").json() == {"ok": True}
    if overflow:
        saved = recovery_payloads(tmp_path)
        assert {entry["queue_name"] for entry in saved} == {"log_queue", "summary_queue"}
        assert all(entry["events"][0]["user_id"] == 1 for entry in saved)
    else:
        assert log_q.get(timeout=0.2).path == "/api/notes"
        assert summary_q.get(timeout=0.2)["user_id"] == 1
