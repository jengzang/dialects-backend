import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

from app.common.path import VOCABULARY_DB_PATH

BACKUP_DIR = Path(VOCABULARY_DB_PATH).parent / "backups"
BACKUP_INTERVAL_SECONDS = 3 * 3600  # 3 hours
RETENTION_DAYS = 7

_backup_lock = threading.Lock()
_backup_thread: threading.Thread | None = None
_backup_stop_event: threading.Event | None = None


def _run_backup() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"vocabulary_{timestamp}.db"

    src = sqlite3.connect(VOCABULARY_DB_PATH)
    try:
        dst_conn = sqlite3.connect(str(dst))
        try:
            src.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src.close()

    print(f"[backup] {dst.name} ({dst.stat().st_size} bytes)")


def _run_cleanup() -> None:
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    removed = 0
    for f in sorted(BACKUP_DIR.glob("vocabulary_*.db")):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            pass
    if removed:
        print(f"[backup] cleaned up {removed} old backup(s)")


def _periodic_backup(stop_event: threading.Event) -> None:
    while not stop_event.wait(BACKUP_INTERVAL_SECONDS):
        try:
            _run_backup()
            _run_cleanup()
        except Exception as exc:
            print(f"[backup] error: {exc}")


def start_backup_scheduler() -> None:
    global _backup_thread, _backup_stop_event

    with _backup_lock:
        if _backup_thread and _backup_thread.is_alive():
            return

        _backup_stop_event = threading.Event()
        _backup_thread = threading.Thread(
            target=_periodic_backup,
            args=(_backup_stop_event,),
            daemon=True,
            name="vocab-backup",
        )
        _backup_thread.start()

    print(f"[backup] scheduler started (interval={BACKUP_INTERVAL_SECONDS // 3600}h, "
          f"retention={RETENTION_DAYS}d, dir={BACKUP_DIR})")


def stop_backup_scheduler() -> None:
    global _backup_thread, _backup_stop_event

    with _backup_lock:
        stop_event = _backup_stop_event
        thread = _backup_thread
        _backup_stop_event = None
        _backup_thread = None

    if stop_event is not None:
        stop_event.set()

    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)
