"""
cluster 任务状态与结果文件服务。

任务进度存在 `task_manager` 里，最终结果写入 `result.json`。
这一层专门负责两者的读写衔接。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.tools.cluster.config import TASK_TOOL_NAME
from app.tools.config import (
    CLEANUP_POLICY_CLUSTER_JOB,
    CLUSTER_JOB_TTL_SECONDS,
)
from app.tools.file_manager import file_manager
from app.tools.task_manager import task_manager


def normalize_task_status(raw_status: Any) -> str:
    """兼容枚举和普通字符串两种状态表示。"""
    if hasattr(raw_status, "value"):
        return str(raw_status.value)
    return str(raw_status or "")


def task_result_path(task_id: str) -> Path:
    """返回某个 cluster 任务对应的结果文件路径。"""
    return file_manager.get_task_dir(task_id, TASK_TOOL_NAME) / "result.json"


def write_result(task_id: str, result: Dict[str, Any]) -> Path:
    """把聚类结果写成格式化 JSON，便于后续接口读取和人工排查。"""
    result_path = task_result_path(task_id)
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    return result_path


def touch_cluster_task_cleanup(task_id: str, reason: str) -> None:
    """cluster 任务目录统一按 2 小时保留。"""
    task_manager.update_task_cleanup(
        task_id,
        policy_key=CLEANUP_POLICY_CLUSTER_JOB,
        armed=True,
        terminal=True,
        ttl_seconds=CLUSTER_JOB_TTL_SECONDS,
        reason=reason,
    )


def get_task_status_payload(task_id: str) -> Optional[Dict[str, Any]]:
    """把 task_manager 的内部状态转换成轮询接口返回结构。"""
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
        "execution_time_ms": (task.get("data") or {}).get("execution_time_ms"),
        "performance": (task.get("data") or {}).get("performance"),
    }


def get_cluster_result(task_id: str) -> Optional[Dict[str, Any]]:
    """读取任务已经落盘的最终结果；若未完成则返回 None。"""
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
    """统一判断任务是否已删除、已取消或被请求取消。"""
    task = task_manager.get_task(task_id)
    if not task:
        return True
    if normalize_task_status(task.get("status")) == "canceled":
        return True
    return bool((task.get("data") or {}).get("cancel_requested"))
