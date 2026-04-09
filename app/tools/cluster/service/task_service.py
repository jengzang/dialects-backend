"""
Cluster task and result storage services.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.tools.cluster.config import TASK_TOOL_NAME
from app.tools.file_manager import file_manager
from app.tools.task_manager import task_manager


def normalize_task_status(raw_status: Any) -> str:
    if hasattr(raw_status, "value"):
        return str(raw_status.value)
    return str(raw_status or "")


def task_result_path(task_id: str) -> Path:
    return file_manager.get_task_dir(task_id, TASK_TOOL_NAME) / "result.json"


def write_result(task_id: str, result: Dict[str, Any]) -> Path:
    result_path = task_result_path(task_id)
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    return result_path


def get_task_status_payload(task_id: str) -> Optional[Dict[str, Any]]:
    task = task_manager.get_task(task_id)
    if not task:
        return None

    return {
        "task_id": task_id,
        "status": normalize_task_status(task.get("status")),
        "progress": float(task.get("progress", 0.0)),
        "message": str(task.get("message") or ""),
        "created_at": float(task.get("created_at", 0.0)),
        "updated_at": float(task.get("updated_at", 0.0)),
        "summary": (task.get("data") or {}).get("summary"),
    }


def get_cluster_result(task_id: str) -> Optional[Dict[str, Any]]:
    task = task_manager.get_task(task_id)
    if not task:
        return None

    result_path = (task.get("data") or {}).get("result_path")
    if not result_path:
        return None

    path = Path(result_path)
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def is_cancel_requested(task_id: str) -> bool:
    task = task_manager.get_task(task_id)
    if not task:
        return True
    if normalize_task_status(task.get("status")) == "canceled":
        return True
    return bool((task.get("data") or {}).get("cancel_requested"))
