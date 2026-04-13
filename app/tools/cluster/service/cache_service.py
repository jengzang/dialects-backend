"""
Cluster cache orchestration helpers.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Optional

from app.common.config import _RUN_TYPE
from app.redis_client import sync_redis_client
from app.tools.cluster.config import INFLIGHT_CACHE_TTL_SECONDS, RESULT_CACHE_TTL_SECONDS


def get_cluster_cache_sync(key: str) -> Optional[Any]:
    try:
        cached_val = sync_redis_client.get(key)
        if cached_val:
            if _RUN_TYPE == "WEB":
                print(f"[Cluster Cache] Hit(sync): {key}")
            return json.loads(cached_val)
    except Exception as exc:
        print(f"[X] Cluster Cache Read Error(sync): {exc}")
    return None


def set_cluster_cache_sync(key: str, data: Any, expire_seconds: int):
    try:
        sync_redis_client.set(
            key,
            json.dumps(data, ensure_ascii=False),
            ex=expire_seconds,
        )
        if _RUN_TYPE == "WEB":
            print(f"[SAVE] [Cluster Cache] Set(sync): {key}")
    except Exception as exc:
        print(f"[X] Cluster Cache Write Error(sync): {exc}")


def delete_cluster_cache_sync(key: str):
    try:
        sync_redis_client.delete(key)
    except Exception as exc:
        print(f"[X] Cluster Cache Delete Error(sync): {exc}")


def _hash_payload(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_cluster_job_hash(snapshot: Dict[str, Any], dialects_db: str) -> str:
    normalized_groups = []
    for group in snapshot.get("groups") or []:
        normalized_groups.append(
            {
                "label": group.get("label"),
                "compare_dimension": group.get("compare_dimension"),
                "resolved_chars": list(group.get("resolved_chars") or []),
                "group_weight": float(group.get("group_weight", 1.0)),
                "use_phonetic_values": bool(group.get("use_phonetic_values", False)),
                "phonetic_value_weight": float(group.get("phonetic_value_weight", 0.2)),
            }
        )

    normalized_payload = {
        "groups": normalized_groups,
        "matched_locations": list(
            (snapshot.get("location_resolution") or {}).get("matched_locations") or []
        ),
        "clustering": snapshot.get("clustering") or {},
        "dialects_db": str(dialects_db),
    }
    return _hash_payload(normalized_payload)


def build_cluster_result_cache_key(job_hash: str) -> str:
    return f"cluster:result:v1:{job_hash}"


def build_cluster_inflight_key(job_hash: str) -> str:
    return f"cluster:inflight:v1:{job_hash}"


def get_cached_cluster_result(job_hash: str) -> Optional[Dict[str, Any]]:
    cached = get_cluster_cache_sync(build_cluster_result_cache_key(job_hash))
    return cached if isinstance(cached, dict) else None


def set_cached_cluster_result(job_hash: str, result: Dict[str, Any]):
    set_cluster_cache_sync(
        build_cluster_result_cache_key(job_hash),
        result,
        expire_seconds=RESULT_CACHE_TTL_SECONDS,
    )


def get_inflight_task_id(job_hash: str) -> Optional[str]:
    cached = get_cluster_cache_sync(build_cluster_inflight_key(job_hash))
    if not isinstance(cached, dict):
        return None
    task_id = cached.get("task_id")
    return str(task_id) if task_id else None


def set_inflight_task_id(job_hash: str, task_id: str):
    set_cluster_cache_sync(
        build_cluster_inflight_key(job_hash),
        {"task_id": task_id},
        expire_seconds=INFLIGHT_CACHE_TTL_SECONDS,
    )


def clear_inflight_task_id(job_hash: str, task_id: Optional[str] = None):
    if task_id:
        current = get_inflight_task_id(job_hash)
        if current and current != task_id:
            return
    delete_cluster_cache_sync(build_cluster_inflight_key(job_hash))


def annotate_cluster_result_cache(
    result: Dict[str, Any],
    *,
    job_hash: str,
    cache_hit: bool,
    cache_source: str,
) -> Dict[str, Any]:
    annotated = copy.deepcopy(result)
    metadata = dict(annotated.get("metadata") or {})
    metadata.update(
        {
            "job_hash": job_hash,
            "cache_hit": bool(cache_hit),
            "cache_source": cache_source,
        }
    )
    annotated["metadata"] = metadata
    return annotated
