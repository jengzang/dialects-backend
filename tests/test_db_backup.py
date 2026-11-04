"""Database backup scheduler: schedule seeding, atomic publish, cleanup."""

import os
import sqlite3
from datetime import datetime, timedelta

import app.lifecycle.db_backup as db_backup
from app.lifecycle.db_backup import _Config


def _config(tmp_path, interval_seconds=6 * 3600):
    db_path = tmp_path / "vocabulary.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (x)")
    conn.commit()
    conn.close()
    return _Config("vocabulary", str(db_path), interval_seconds, 7)


def _snapshot(cfg, name, age):
    path = cfg.dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    timestamp = (datetime.now() - age).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


def test_schedule_runs_immediately_without_history(tmp_path):
    cfg = _config(tmp_path)
    now = datetime.now()
    assert db_backup._initial_next_run(cfg, now) == now


def test_schedule_waits_for_remaining_interval(tmp_path):
    cfg = _config(tmp_path)
    now = datetime.now()
    _snapshot(cfg, "vocabulary_20261104_000000.db", timedelta(hours=1))
    next_run = db_backup._initial_next_run(cfg, now)
    assert abs((next_run - (now + timedelta(hours=5))).total_seconds()) < 1


def test_schedule_runs_when_overdue(tmp_path):
    cfg = _config(tmp_path)
    now = datetime.now()
    _snapshot(cfg, "vocabulary_20261104_000000.db", timedelta(hours=7))
    assert db_backup._initial_next_run(cfg, now) == now


def test_empty_snapshot_is_not_treated_as_latest(tmp_path):
    cfg = _config(tmp_path)
    now = datetime.now()
    _snapshot(cfg, "vocabulary_20261104_000000.db", timedelta(hours=7))
    (cfg.dir / "vocabulary_20261105_000000.db").write_bytes(b"")
    assert db_backup._initial_next_run(cfg, now) == now


def test_scan_survives_unrepresentable_mtime(tmp_path, monkeypatch):
    cfg = _config(tmp_path)
    now = datetime.now()
    _snapshot(cfg, "vocabulary_20261104_000000.db", timedelta(hours=7))
    bad = cfg.dir / "vocabulary_20261105_000000.db"
    bad.write_bytes(b"x")
    future = (now + timedelta(hours=1)).timestamp()
    os.utime(bad, (future, future))

    class FakeDatetime(datetime):
        @classmethod
        def fromtimestamp(cls, timestamp, tz=None):
            if timestamp > now.timestamp():
                raise ValueError("year out of range")
            return datetime.fromtimestamp(timestamp, tz)

    monkeypatch.setattr(db_backup, "datetime", FakeDatetime)
    assert db_backup._initial_next_run(cfg, now) == now


def test_backup_publishes_single_snapshot(tmp_path):
    cfg = _config(tmp_path)
    db_backup._backup_one(cfg)
    names = [p.name for p in cfg.dir.iterdir()]
    assert len(names) == 1
    assert names[0].startswith("vocabulary_") and names[0].endswith(".db")
    conn = sqlite3.connect(cfg.dir / names[0])
    try:
        assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 0
    finally:
        conn.close()


def test_cleanup_removes_abandoned_tmp_after_one_day(tmp_path):
    cfg = _config(tmp_path)
    cfg.dir.mkdir(parents=True)
    old = (datetime.now() - timedelta(days=2)).timestamp()
    for name in (
        ".vocabulary_20200101_000000_1.db.tmp",
        ".vocabulary_20200101_000000_1.db.tmp-journal",
    ):
        path = cfg.dir / name
        path.write_text("x")
        os.utime(path, (old, old))
    db_backup._cleanup_one(cfg)
    assert list(cfg.dir.iterdir()) == []
