import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from app.common.path import VOCABULARY_DB_PATH, USER_DATABASE_PATH, SUPPLE_DB_PATH


@dataclass
class _Config:
    name: str
    db_path: str
    interval_seconds: int
    retention_days: int

    @property
    def dir(self) -> Path:
        return Path(self.db_path).parent / "backups" / self.name


CONFIGS = [
    _Config("vocabulary", VOCABULARY_DB_PATH, interval_seconds=3 * 3600, retention_days=7),
    _Config("auth", USER_DATABASE_PATH, interval_seconds=24 * 3600, retention_days=7),
    _Config("supplements", SUPPLE_DB_PATH, interval_seconds=24 * 3600, retention_days=7),
]

_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None


def _backup_one(cfg: _Config) -> None:
    if not Path(cfg.db_path).exists():
        return
    cfg.dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = cfg.dir / f"{cfg.name}_{timestamp}.db"

    src = sqlite3.connect(cfg.db_path)
    try:
        dst_conn = sqlite3.connect(str(dst))
        try:
            src.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src.close()

    print(f"[backup:{cfg.name}] {dst.name} ({dst.stat().st_size} bytes)")


def _cleanup_one(cfg: _Config) -> None:
    cutoff = datetime.now() - timedelta(days=cfg.retention_days)
    removed = 0
    for f in sorted(cfg.dir.glob(f"{cfg.name}_*.db")):
        try:
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            pass
    if removed:
        print(f"[backup:{cfg.name}] cleaned up {removed} old backup(s)")


def _periodic_backup(stop_event: threading.Event) -> None:
    next_run = {c.name: datetime.now() for c in CONFIGS}
    while not stop_event.wait(60):
        now = datetime.now()
        for c in CONFIGS:
            if now >= next_run[c.name]:
                try:
                    _backup_one(c)
                    _cleanup_one(c)
                except Exception as exc:
                    print(f"[backup:{c.name}] error: {exc}")
                next_run[c.name] = now + timedelta(seconds=c.interval_seconds)


def start_backup_scheduler() -> None:
    global _thread, _stop_event

    with _lock:
        if _thread and _thread.is_alive():
            return

        _stop_event = threading.Event()
        _thread = threading.Thread(
            target=_periodic_backup,
            args=(_stop_event,),
            daemon=True,
            name="db-backup",
        )
        _thread.start()

    for c in CONFIGS:
        print(f"[backup:{c.name}] interval={c.interval_seconds // 3600}h, "
              f"retention={c.retention_days}d, dir={c.dir}")


def stop_backup_scheduler() -> None:
    global _thread, _stop_event

    with _lock:
        stop_evt = _stop_event
        th = _thread
        _stop_event = None
        _thread = None

    if stop_evt is not None:
        stop_evt.set()

    if th is not None and th.is_alive():
        th.join(timeout=1.0)
