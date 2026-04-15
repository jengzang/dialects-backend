"""
cluster 缓存协调层。

这里负责三件事：
1. 统一读写 Redis；
2. 生成 job_hash、结果缓存 key、inflight key；
3. 在返回结果里补充缓存命中标记，便于前端展示和调试。
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Optional

from app.common.config import _RUN_TYPE
from app.redis_client import sync_redis_client
from app.tools.cluster.config import (
    INFLIGHT_CACHE_TTL_SECONDS,
    RESULT_CACHE_TTL_SECONDS,
    STAGED_DISTANCE_TTL_SECONDS,
    STAGED_PREPARE_TTL_SECONDS,
)


def get_cluster_cache_sync(key: str) -> Optional[Any]:
    """同步读取 Redis，并把 JSON 字符串反序列化成 Python 对象。"""
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
    """同步写入 Redis，cluster 统一使用 UTF-8 JSON 作为缓存载体。"""
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
    """删除指定缓存 key。"""
    try:
        sync_redis_client.delete(key)
    except Exception as exc:
        print(f"[X] Cluster Cache Delete Error(sync): {exc}")


def _hash_payload(payload: Dict[str, Any]) -> str:
    """对归一化后的 payload 计算稳定哈希。"""
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_cluster_job_hash(
    snapshot: Dict[str, Any],
    dialects_db: str,
    query_db: Optional[str] = None,
) -> str:
    """
    只基于真正影响聚类结果的字段生成 job_hash。

    这样结果缓存和 inflight 去重才能跨 task_id、跨请求顺序稳定命中。
    """
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
        "query_db": str(query_db or ""),
    }
    return _hash_payload(normalized_payload)


def build_cluster_prepare_hash(
    snapshot: Dict[str, Any],
    dialects_db: str,
    query_db: Optional[str] = None,
) -> str:
    """基于标准化 snapshot 生成 prepare 阶段的稳定哈希。"""
    normalized_groups = []
    for group in snapshot.get("groups") or []:
        normalized_groups.append(
            {
                "label": group.get("label"),
                "source_mode": group.get("source_mode"),
                "table_name": group.get("table_name"),
                "path_strings": list(group.get("path_strings") or []),
                "column": list(group.get("column") or []),
                "combine_query": bool(group.get("combine_query", False)),
                "filters": group.get("filters") or {},
                "exclude_columns": list(group.get("exclude_columns") or []),
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
        "dialects_db": str(dialects_db),
        "query_db": str(query_db or ""),
    }
    return _hash_payload(normalized_payload)


def build_cluster_distance_hash(prepare_hash: str, phoneme_mode: str) -> str:
    """基于 prepare_hash 与 phoneme_mode 生成 distance 阶段的稳定哈希。"""
    return _hash_payload(
        {
            "prepare_hash": str(prepare_hash),
            "phoneme_mode": str(phoneme_mode),
        }
    )


def build_cluster_result_cache_key(job_hash: str) -> str:
    """结果缓存 key。"""
    return f"cluster:result:v1:{job_hash}"


def build_cluster_prepare_cache_key(prepare_hash: str) -> str:
    """prepare artifact 摘要缓存 key。"""
    return f"cluster:prepare:v1:{prepare_hash}"


def build_cluster_distance_cache_key(distance_hash: str) -> str:
    """distance artifact 摘要缓存 key。"""
    return f"cluster:distance:v1:{distance_hash}"


def build_cluster_inflight_key(job_hash: str) -> str:
    """运行中任务去重 key。"""
    return f"cluster:inflight:v1:{job_hash}"


def build_cluster_prepare_inflight_key(prepare_hash: str) -> str:
    """prepare 阶段运行中任务去重 key。"""
    return f"cluster:prepare:inflight:v1:{prepare_hash}"


def build_cluster_distance_inflight_key(distance_hash: str) -> str:
    """distance 阶段运行中任务去重 key。"""
    return f"cluster:distance:inflight:v1:{distance_hash}"


def get_cached_cluster_result(job_hash: str) -> Optional[Dict[str, Any]]:
    """读取完整聚类结果缓存。"""
    cached = get_cluster_cache_sync(build_cluster_result_cache_key(job_hash))
    return cached if isinstance(cached, dict) else None


def get_cached_prepare_artifact(prepare_hash: str) -> Optional[Dict[str, Any]]:
    """读取 prepare artifact 摘要缓存。"""
    cached = get_cluster_cache_sync(build_cluster_prepare_cache_key(prepare_hash))
    return cached if isinstance(cached, dict) else None


def get_cached_distance_artifact(distance_hash: str) -> Optional[Dict[str, Any]]:
    """读取 distance artifact 摘要缓存。"""
    cached = get_cluster_cache_sync(build_cluster_distance_cache_key(distance_hash))
    return cached if isinstance(cached, dict) else None


def set_cached_cluster_result(job_hash: str, result: Dict[str, Any]):
    """写入完整聚类结果缓存。"""
    set_cluster_cache_sync(
        build_cluster_result_cache_key(job_hash),
        result,
        expire_seconds=RESULT_CACHE_TTL_SECONDS,
    )


def set_cached_prepare_artifact(prepare_hash: str, payload: Dict[str, Any]):
    """写入 prepare artifact 摘要缓存。"""
    set_cluster_cache_sync(
        build_cluster_prepare_cache_key(prepare_hash),
        payload,
        expire_seconds=STAGED_PREPARE_TTL_SECONDS,
    )


def set_cached_distance_artifact(distance_hash: str, payload: Dict[str, Any]):
    """写入 distance artifact 摘要缓存。"""
    set_cluster_cache_sync(
        build_cluster_distance_cache_key(distance_hash),
        payload,
        expire_seconds=STAGED_DISTANCE_TTL_SECONDS,
    )


def _get_inflight_task_id_by_key(key: str) -> Optional[str]:
    cached = get_cluster_cache_sync(key)
    if not isinstance(cached, dict):
        return None
    task_id = cached.get("task_id")
    return str(task_id) if task_id else None


def get_inflight_task_id(job_hash: str) -> Optional[str]:
    """查询当前是否已有完全相同的请求正在运行。"""
    return _get_inflight_task_id_by_key(build_cluster_inflight_key(job_hash))


def get_prepare_inflight_task_id(prepare_hash: str) -> Optional[str]:
    """查询当前是否已有完全相同的 prepare 正在运行。"""
    return _get_inflight_task_id_by_key(build_cluster_prepare_inflight_key(prepare_hash))


def get_distance_inflight_task_id(distance_hash: str) -> Optional[str]:
    """查询当前是否已有完全相同的 distance 正在运行。"""
    return _get_inflight_task_id_by_key(build_cluster_distance_inflight_key(distance_hash))


def set_inflight_task_id(job_hash: str, task_id: str):
    """登记运行中的 task_id，避免重复计算。"""
    set_cluster_cache_sync(
        build_cluster_inflight_key(job_hash),
        {"task_id": task_id},
        expire_seconds=INFLIGHT_CACHE_TTL_SECONDS,
    )


def set_prepare_inflight_task_id(prepare_hash: str, task_id: str):
    """登记运行中的 prepare task_id。"""
    set_cluster_cache_sync(
        build_cluster_prepare_inflight_key(prepare_hash),
        {"task_id": task_id},
        expire_seconds=INFLIGHT_CACHE_TTL_SECONDS,
    )


def set_distance_inflight_task_id(distance_hash: str, task_id: str):
    """登记运行中的 distance task_id。"""
    set_cluster_cache_sync(
        build_cluster_distance_inflight_key(distance_hash),
        {"task_id": task_id},
        expire_seconds=INFLIGHT_CACHE_TTL_SECONDS,
    )


def _clear_inflight_task_id_by_key(key: str, task_id: Optional[str] = None):
    if task_id:
        current = _get_inflight_task_id_by_key(key)
        if current and current != task_id:
            return
    delete_cluster_cache_sync(key)


def clear_inflight_task_id(job_hash: str, task_id: Optional[str] = None):
    """清理 inflight 标记；可选校验 task_id，避免误删其他任务。"""
    _clear_inflight_task_id_by_key(build_cluster_inflight_key(job_hash), task_id=task_id)


def clear_prepare_inflight_task_id(prepare_hash: str, task_id: Optional[str] = None):
    """清理 prepare inflight 标记。"""
    _clear_inflight_task_id_by_key(
        build_cluster_prepare_inflight_key(prepare_hash),
        task_id=task_id,
    )


def clear_distance_inflight_task_id(distance_hash: str, task_id: Optional[str] = None):
    """清理 distance inflight 标记。"""
    _clear_inflight_task_id_by_key(
        build_cluster_distance_inflight_key(distance_hash),
        task_id=task_id,
    )


def annotate_cluster_result_cache(
    result: Dict[str, Any],
    *,
    job_hash: str,
    cache_hit: bool,
    cache_source: str,
) -> Dict[str, Any]:
    """把缓存命中状态写进 metadata，方便前端与日志观察。"""
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
