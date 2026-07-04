from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from app.tools.cluster.config import (
    CLUSTER_EXECUTOR_DIRNAME,
    CLUSTER_EXECUTOR_PENDING_DIRNAME,
    CLUSTER_EXECUTOR_PROCESSING_DIRNAME,
    CLUSTER_EXECUTOR_COMPLETED_DIRNAME,
    CLUSTER_EXECUTOR_FAILED_DIRNAME,
    TASK_TOOL_NAME,
)
from app.tools.file_manager import file_manager


def _executor_root() -> Path:
    root = file_manager.get_tool_dir(TASK_TOOL_NAME) / CLUSTER_EXECUTOR_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _queue_dir(name: str) -> Path:
    path = _executor_root() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def pending_dir() -> Path:
    return _queue_dir(CLUSTER_EXECUTOR_PENDING_DIRNAME)


def processing_dir() -> Path:
    return _queue_dir(CLUSTER_EXECUTOR_PROCESSING_DIRNAME)


def completed_dir() -> Path:
    return _queue_dir(CLUSTER_EXECUTOR_COMPLETED_DIRNAME)


def failed_dir() -> Path:
    return _queue_dir(CLUSTER_EXECUTOR_FAILED_DIRNAME)


def _job_path(state_dir: Path, job_id: str) -> Path:
    return state_dir / f"{job_id}.json"


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def _read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def build_job_envelope(*, job_type: str, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "job_id": f"cluster_exec_{uuid.uuid4().hex}",
        "job_type": str(job_type),
        "task_id": str(task_id),
        "created_at": time.time(),
        "payload": dict(payload),
    }


def enqueue_job(*, job_type: str, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    envelope = build_job_envelope(job_type=job_type, task_id=task_id, payload=payload)
    _atomic_write_json(_job_path(pending_dir(), envelope["job_id"]), envelope)
    return envelope


def claim_next_job() -> Optional[Dict[str, Any]]:
    candidates = sorted(pending_dir().glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name))
    for path in candidates:
        target = _job_path(processing_dir(), path.stem)
        try:
            os.replace(path, target)
        except FileNotFoundError:
            continue
        except OSError:
            continue
        payload = _read_json(target)
        payload["claimed_at"] = time.time()
        _atomic_write_json(target, payload)
        return payload
    return None


def mark_job_completed(job_id: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    source = _job_path(processing_dir(), job_id)
    payload = _read_json(source)
    payload["completed_at"] = time.time()
    payload["status"] = "completed"
    if extra:
        payload.update(extra)
    target = _job_path(completed_dir(), job_id)
    _atomic_write_json(target, payload)
    source.unlink(missing_ok=True)
    return payload


def mark_job_failed(job_id: str, *, error: str) -> Dict[str, Any]:
    source = _job_path(processing_dir(), job_id)
    payload = _read_json(source)
    payload["failed_at"] = time.time()
    payload["status"] = "failed"
    payload["error"] = str(error)
    target = _job_path(failed_dir(), job_id)
    _atomic_write_json(target, payload)
    source.unlink(missing_ok=True)
    return payload


def requeue_processing_jobs() -> int:
    count = 0
    for path in processing_dir().glob("*.json"):
        target = _job_path(pending_dir(), path.stem)
        try:
            os.replace(path, target)
            count += 1
        except OSError:
            continue
    return count
