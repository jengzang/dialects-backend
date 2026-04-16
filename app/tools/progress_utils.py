"""
Shared progress contract helpers for tools tasks and jobs.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any, Callable, Optional


ACTIVE_TASK_STATUSES = {"processing"}
ACTIVE_JOB_STATUSES = {"queued", "running"}


CHECK_ANALYZE_HEARTBEAT_SECONDS = 5.0
CHECK_ANALYZE_TIMEOUT_SECONDS = 3 * 60.0
JYUT2IPA_HEARTBEAT_SECONDS = 5.0
JYUT2IPA_TIMEOUT_SECONDS = 5 * 60.0
MERGE_HEARTBEAT_SECONDS = 10.0
MERGE_TIMEOUT_SECONDS = 8 * 60.0
PRAAT_HEARTBEAT_SECONDS = 10.0
PRAAT_TIMEOUT_SECONDS = 15 * 60.0


def clamp_progress(progress: Any, *, scale: float = 1.0) -> float:
    try:
        value = float(progress) * scale
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, min(100.0, value))


def normalize_public_progress(progress: Any) -> float:
    try:
        value = float(progress)
    except (TypeError, ValueError):
        value = 0.0
    if 0.0 <= value <= 1.0:
        return clamp_progress(value, scale=100.0)
    return clamp_progress(value)


def timestamp_to_datetime(timestamp: Any) -> Optional[datetime]:
    try:
        if timestamp is None:
            return None
        return datetime.fromtimestamp(float(timestamp), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def iso_to_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def build_task_progress_payload(task: dict) -> dict:
    return {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "progress": clamp_progress(task.get("progress")),
        "message": task.get("message", ""),
        "stage": task.get("stage"),
        "updated_at": timestamp_to_datetime(task.get("updated_at")),
    }


def build_job_progress_payload(job_id: str, job: dict) -> dict:
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "progress": normalize_public_progress(job.get("progress")),
        "stage": job.get("stage"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


def mark_task_ready(task_manager, task_id: str, *, message: str, stage: str = "ready", data: Optional[dict] = None) -> None:
    kwargs = {
        "status": "pending",
        "progress": 0.0,
        "message": message,
        "stage": stage,
    }
    if data is not None:
        kwargs["data"] = data
    task_manager.update_task(task_id, **kwargs)


def maybe_timeout_task(
    task_manager,
    task_id: str,
    *,
    timeout_seconds: float,
    failure_status: str,
    timeout_message: str,
    on_timeout: Optional[Callable[[str], None]] = None,
    now_ts: Optional[float] = None,
) -> Optional[dict]:
    task = task_manager.get_task(task_id)
    if not task:
        return None

    if str(task.get("status")) not in ACTIVE_TASK_STATUSES:
        return task

    now_ts = time.time() if now_ts is None else now_ts
    updated_at = float(task.get("updated_at") or task.get("created_at") or 0.0)
    if (now_ts - updated_at) <= timeout_seconds:
        return task

    task_manager.update_task(
        task_id,
        status=failure_status,
        message=timeout_message,
        error=timeout_message,
    )
    if on_timeout is not None:
        on_timeout(task_id)
    return task_manager.get_task(task_id) or task


def maybe_timeout_praat_job(
    task_manager,
    task_id: str,
    job_id: str,
    *,
    timeout_seconds: float,
    update_job_status,
    find_job_by_id,
    on_timeout: Optional[Callable[[str], None]] = None,
    now_dt: Optional[datetime] = None,
) -> tuple[Optional[dict], Optional[dict]]:
    task = task_manager.get_task(task_id)
    if not task:
        return None, None

    job = find_job_by_id(task, job_id)
    if not job or str(job.get("status")) not in ACTIVE_JOB_STATUSES:
        return task, job

    now_dt = datetime.now(UTC) if now_dt is None else now_dt
    updated_at = iso_to_datetime(job.get("updated_at")) or iso_to_datetime(job.get("created_at"))
    if updated_at is None or (now_dt - updated_at).total_seconds() <= timeout_seconds:
        return task, job

    timeout_message = "Praat job timeout: no heartbeat received within the expected window"
    update_job_status(
        task_manager,
        task_id,
        job_id,
        status="error",
        error={
            "code": "PRAAT_ANALYSIS_FAILED",
            "message": timeout_message,
            "detail": {"reason": "timeout"},
        },
    )
    if on_timeout is not None:
        on_timeout(task_id)

    task = task_manager.get_task(task_id)
    if not task:
        return None, None
    return task, find_job_by_id(task, job_id)


class ProgressHeartbeat:
    """Background heartbeat for long-running tasks/jobs."""

    def __init__(self, interval_seconds: float, beat: Callable[[], None]):
        self.interval_seconds = interval_seconds
        self._beat = beat
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def __enter__(self):
        def runner():
            while not self._stop_event.wait(self.interval_seconds):
                try:
                    self._beat()
                except Exception as exc:  # pragma: no cover - best effort heartbeat
                    print(f"[ProgressHeartbeat] beat failed: {exc}")

        self._thread = threading.Thread(target=runner, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds)
