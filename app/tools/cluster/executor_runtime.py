from __future__ import annotations

import threading
import time
from typing import Any, Dict

from app.tools.cluster.config import CLUSTER_EXECUTOR_POLL_INTERVAL_SECONDS
from app.tools.cluster.executor_queue import (
    claim_next_job,
    enqueue_job,
    mark_job_completed,
    mark_job_failed,
    requeue_processing_jobs,
)

_executor_lock = threading.Lock()
_executor_thread: threading.Thread | None = None
_executor_stop_event: threading.Event | None = None


def _dispatch_job(job: Dict[str, Any]) -> None:
    job_type = str(job["job_type"])
    payload = dict(job.get("payload") or {})
    task_id = str(job["task_id"])

    if job_type == "cluster_job":
        from app.tools.cluster.service.cluster_service import run_cluster_job

        run_cluster_job(task_id, payload["dialects_db"], payload["query_db"])
        return

    if job_type == "staged_prepare":
        from app.tools.cluster.service.staged_session_service import run_prepare_task

        run_prepare_task(task_id)
        return

    if job_type == "staged_distance":
        from app.tools.cluster.service.staged_session_service import run_distance_task

        run_distance_task(task_id, payload["phoneme_mode"])
        return

    if job_type == "staged_cluster":
        from app.tools.cluster.service.staged_session_service import run_cluster_task

        run_cluster_task(task_id, payload["distance_hash"], payload["clustering_config"])
        return

    raise ValueError(f"Unknown cluster executor job_type: {job_type}")


def _executor_loop(stop_event: threading.Event) -> None:
    recovered = requeue_processing_jobs()
    if recovered:
        print(f"[ClusterExecutor] Requeued {recovered} processing job(s) on startup")

    while not stop_event.is_set():
        job = claim_next_job()
        if job is None:
            stop_event.wait(CLUSTER_EXECUTOR_POLL_INTERVAL_SECONDS)
            continue

        job_id = str(job["job_id"])
        try:
            _dispatch_job(job)
            mark_job_completed(job_id)
        except Exception as exc:
            print(f"[ClusterExecutor] Job {job_id} failed: {exc}")
            mark_job_failed(job_id, error=str(exc))


def start_cluster_executor() -> None:
    global _executor_thread, _executor_stop_event
    with _executor_lock:
        if _executor_thread and _executor_thread.is_alive():
            return
        _executor_stop_event = threading.Event()
        _executor_thread = threading.Thread(
            target=_executor_loop,
            args=(_executor_stop_event,),
            daemon=True,
            name="cluster_executor",
        )
        _executor_thread.start()
        print("[ClusterExecutor] Started single-instance serial executor")


def stop_cluster_executor() -> None:
    global _executor_thread, _executor_stop_event
    with _executor_lock:
        thread = _executor_thread
        stop_event = _executor_stop_event
        _executor_thread = None
        _executor_stop_event = None
    if stop_event is not None:
        stop_event.set()
    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)
        print("[ClusterExecutor] Stopped serial executor")


__all__ = [
    "enqueue_job",
    "start_cluster_executor",
    "stop_cluster_executor",
]
