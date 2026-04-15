"""
cluster staged token 服务。

这一层不再维护 session，而是围绕全局 hash artifact 工作：
- preview 产出并持久化 `prepare_hash` 对应的轻量 snapshot；
- prepare 基于 `prepare_hash` 生成可复用的编码结果；
- distance 基于 `prepare_hash + phoneme_mode` 生成距离矩阵；
- cluster 基于 `distance_hash + clustering` 生成最终 `result_hash`。
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from app.common.path import DIALECTS_DB_USER, QUERY_DB_USER
from app.tools.cluster.config import (
    STAGED_ARTIFACT_ROOT_DIRNAME,
    STAGED_DISTANCE_TTL_SECONDS,
    STAGED_PREPARE_TTL_SECONDS,
    STAGED_PREVIEW_TTL_SECONDS,
    STAGED_RESULT_TTL_SECONDS,
    TASK_TOOL_NAME,
)
from app.tools.cluster.service.cache_service import (
    annotate_cluster_result_cache,
    build_cluster_distance_hash,
    build_cluster_job_hash,
    build_cluster_prepare_hash,
    clear_distance_inflight_task_id,
    clear_inflight_task_id,
    clear_prepare_inflight_task_id,
    get_cached_cluster_result,
    get_cached_distance_artifact,
    get_cached_prepare_artifact,
    get_distance_inflight_task_id,
    get_inflight_task_id,
    get_prepare_inflight_task_id,
    set_cached_cluster_result,
    set_cached_distance_artifact,
    set_cached_prepare_artifact,
    set_distance_inflight_task_id,
    set_inflight_task_id,
    set_prepare_inflight_task_id,
)
from app.tools.cluster.service.cluster_service import (
    build_cluster_distance_state,
    build_cluster_final_result,
    build_cluster_prepare_state,
)
from app.tools.cluster.service.result_service import build_task_summary
from app.tools.cluster.service.task_service import get_task_status_payload
from app.tools.file_manager import file_manager
from app.tools.task_manager import TaskStatus, task_manager


class ClusterStageError(Exception):
    """staged token 的统一基类异常。"""


class ClusterStageNotFoundError(ClusterStageError):
    """缺少上游 hash artifact。"""


class ClusterStageConflictError(ClusterStageError):
    """上游阶段仍在处理中，当前无法继续。"""


class ClusterStageValidationError(ClusterStageError):
    """阶段参数不合法。"""


ProgressCallback = Callable[[float, str, Optional[Dict[str, float]]], None]
_ARTIFACT_LOCKS: Dict[str, threading.Lock] = {}
_ARTIFACT_LOCKS_GUARD = threading.Lock()


def _get_artifact_lock(key: str) -> threading.Lock:
    with _ARTIFACT_LOCKS_GUARD:
        lock = _ARTIFACT_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _ARTIFACT_LOCKS[key] = lock
        return lock


def _now_ts() -> float:
    return time.time()


def _enum_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    return value


def _normalize_phoneme_mode(phoneme_mode: Any) -> str:
    return str(_enum_value(phoneme_mode) or "")


def _artifact_root_dir() -> Path:
    root = file_manager.get_tool_dir(TASK_TOOL_NAME) / STAGED_ARTIFACT_ROOT_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _artifact_stage_dir(stage: str) -> Path:
    stage_dir = _artifact_root_dir() / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    return stage_dir


def _touch_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.utime(path, None)


def _touch_artifact_parent_dirs(stage: str) -> None:
    _touch_dir(file_manager.get_tool_dir(TASK_TOOL_NAME))
    _touch_dir(_artifact_root_dir())
    _touch_dir(_artifact_stage_dir(stage))


def _preview_json_path(prepare_hash: str) -> Path:
    return _artifact_stage_dir("preview") / f"{prepare_hash}.json"


def _prepare_json_path(prepare_hash: str) -> Path:
    return _artifact_stage_dir("prepare") / f"{prepare_hash}.json"


def _prepare_npz_path(prepare_hash: str) -> Path:
    return _artifact_stage_dir("prepare") / f"{prepare_hash}.npz"


def _distance_json_path(distance_hash: str) -> Path:
    return _artifact_stage_dir("distance") / f"{distance_hash}.json"


def _distance_npy_path(distance_hash: str) -> Path:
    return _artifact_stage_dir("distance") / f"{distance_hash}.npy"


def _result_json_path(result_hash: str) -> Path:
    return _artifact_stage_dir("result") / f"{result_hash}.json"


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, path)


def _atomic_write_npy(path: Path, matrix: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.tmp.npy")
    np.save(temp_path, matrix)
    os.replace(temp_path, path)


def _atomic_write_npz(path: Path, arrays: Dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.tmp.npz")
    np.savez_compressed(temp_path, **arrays)
    os.replace(temp_path, path)


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _artifact_expired(meta: Optional[Dict[str, Any]], *, current_ts: Optional[float] = None) -> bool:
    if not meta:
        return True
    expires_at = meta.get("expires_at")
    if expires_at is None:
        return False
    return float(expires_at) <= (current_ts or _now_ts())


def _build_preview(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    location_resolution = snapshot.get("location_resolution") or {}
    groups = snapshot.get("groups") or []
    unique_chars: List[str] = []
    for group in groups:
        unique_chars.extend(group.get("resolved_chars") or [])
    requested_dimensions = sorted(
        {group.get("compare_dimension") for group in groups if group.get("compare_dimension")}
    )
    matched_location_count = int(location_resolution.get("matched_location_count", 0))
    estimated_pair_count = matched_location_count * max(matched_location_count - 1, 0) // 2
    estimated_dense_matrix_mb = round(
        float((matched_location_count * matched_location_count * 8) / (1024 * 1024)),
        3,
    )
    return {
        **build_task_summary(snapshot),
        "unique_char_count": len(dict.fromkeys(unique_chars)),
        "requested_dimensions": requested_dimensions,
        "estimated_pair_count": estimated_pair_count,
        "estimated_dense_matrix_mb": estimated_dense_matrix_mb,
    }


def _serialize_dimension_catalogs(dimension_catalogs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    serialized: Dict[str, Dict[str, Any]] = {}
    for dimension, catalog in dimension_catalogs.items():
        serialized[dimension] = {
            "tokens": list(catalog.get("tokens") or []),
            "token_parts": [list(parts) for parts in (catalog.get("token_parts") or [])],
        }
    return serialized


def _deserialize_dimension_catalogs(payload: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    catalogs: Dict[str, Dict[str, Any]] = {}
    for dimension, meta in payload.items():
        tokens = tuple(meta.get("tokens") or [])
        token_parts = tuple(tuple(parts) for parts in (meta.get("token_parts") or []))
        catalogs[dimension] = {
            "tokens": tokens,
            "token_parts": token_parts,
            "token_value_sets": tuple(frozenset(parts) for parts in token_parts),
            "token_to_id": {token: index for index, token in enumerate(tokens)},
            "value_distance_cache": {},
        }
    return catalogs


def _serialize_group_model_meta(group_model: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "label": group_model.get("label"),
        "source_mode": group_model.get("source_mode"),
        "table_name": group_model.get("table_name"),
        "path_strings": group_model.get("path_strings"),
        "column": group_model.get("column"),
        "combine_query": group_model.get("combine_query"),
        "filters": group_model.get("filters"),
        "exclude_columns": group_model.get("exclude_columns"),
        "compare_dimension": group_model.get("compare_dimension"),
        "feature_column": group_model.get("feature_column"),
        "group_weight": group_model.get("group_weight"),
        "use_phonetic_values": group_model.get("use_phonetic_values"),
        "phonetic_value_weight": group_model.get("phonetic_value_weight"),
        "resolved_chars": list(group_model.get("resolved_chars") or []),
        "char_count": int(group_model.get("char_count", 0)),
        "sample_chars": list(group_model.get("sample_chars") or []),
        "cache_hit": bool(group_model.get("cache_hit", False)),
        "cache_key": group_model.get("cache_key"),
        "resolver": group_model.get("resolver"),
        "query_labels": list(group_model.get("query_labels") or []),
        "effective_locations": list(group_model.get("effective_locations") or []),
        "coverage_ratio": float(group_model.get("coverage_ratio", 0.0)),
        "warnings": list(group_model.get("warnings") or []),
    }


def _deserialize_group_model(
    group_meta: Dict[str, Any],
    token_matrix: np.ndarray,
    present_char_counts: np.ndarray,
    dimension_catalogs: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    group_model = dict(group_meta)
    group_model["token_catalog"] = dimension_catalogs[group_meta["compare_dimension"]]
    group_model["token_matrix"] = np.asarray(token_matrix, dtype=np.int32)
    group_model["present_char_counts"] = np.asarray(present_char_counts, dtype=np.int32)
    return group_model


def _prepare_arrays_payload(prepare_state: Dict[str, Any]) -> Dict[str, np.ndarray]:
    arrays: Dict[str, np.ndarray] = {}
    for index, group_model in enumerate(prepare_state.get("group_models") or []):
        arrays[f"group_{index}_token_matrix"] = np.asarray(group_model["token_matrix"], dtype=np.int32)
        arrays[f"group_{index}_present_char_counts"] = np.asarray(
            group_model["present_char_counts"],
            dtype=np.int32,
        )
    for dimension, bucket_model in (prepare_state.get("bucket_models") or {}).items():
        arrays[f"bucket_{dimension}_token_matrix"] = np.asarray(
            bucket_model["token_matrix"],
            dtype=np.int32,
        )
        arrays[f"bucket_{dimension}_present_char_counts"] = np.asarray(
            bucket_model["present_char_counts"],
            dtype=np.int32,
        )
    return arrays


def _prepare_json_payload(prepare_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "matched_locations": list(prepare_state.get("matched_locations") or []),
        "effective_locations": list(prepare_state.get("effective_locations") or []),
        "dropped_locations": list(prepare_state.get("dropped_locations") or []),
        "requested_dimensions": list(prepare_state.get("requested_dimensions") or []),
        "dimension_token_catalogs": _serialize_dimension_catalogs(
            prepare_state.get("dimension_token_catalogs") or {}
        ),
        "group_models": [
            _serialize_group_model_meta(group_model)
            for group_model in (prepare_state.get("group_models") or [])
        ],
        "bucket_models": {
            dimension: _serialize_group_model_meta(bucket_model)
            for dimension, bucket_model in (prepare_state.get("bucket_models") or {}).items()
        },
        "group_diagnostics": prepare_state.get("group_diagnostics") or [],
        "performance": prepare_state.get("performance") or {},
    }


def _distance_json_payload(distance_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "phoneme_mode": distance_state.get("phoneme_mode"),
        "phoneme_mode_params": distance_state.get("phoneme_mode_params") or {},
        "performance": distance_state.get("performance") or {},
    }


def _load_prepare_state_from_payload(meta_payload: Dict[str, Any], npz_path: Path) -> Dict[str, Any]:
    with np.load(npz_path, allow_pickle=False) as npz_file:
        dimension_catalogs = _deserialize_dimension_catalogs(
            meta_payload.get("dimension_token_catalogs") or {}
        )
        group_models = []
        for index, group_meta in enumerate(meta_payload.get("group_models") or []):
            group_models.append(
                _deserialize_group_model(
                    group_meta,
                    npz_file[f"group_{index}_token_matrix"],
                    npz_file[f"group_{index}_present_char_counts"],
                    dimension_catalogs,
                )
            )
        bucket_models: Dict[str, Dict[str, Any]] = {}
        for dimension, group_meta in (meta_payload.get("bucket_models") or {}).items():
            bucket_models[dimension] = _deserialize_group_model(
                group_meta,
                npz_file[f"bucket_{dimension}_token_matrix"],
                npz_file[f"bucket_{dimension}_present_char_counts"],
                dimension_catalogs,
            )

    return {
        "matched_locations": list(meta_payload.get("matched_locations") or []),
        "effective_locations": list(meta_payload.get("effective_locations") or []),
        "dropped_locations": list(meta_payload.get("dropped_locations") or []),
        "requested_dimensions": list(meta_payload.get("requested_dimensions") or []),
        "dimension_token_catalogs": dimension_catalogs,
        "group_models": group_models,
        "bucket_models": bucket_models,
        "group_diagnostics": meta_payload.get("group_diagnostics") or [],
        "performance": meta_payload.get("performance") or {},
    }


def _prepare_summary(prepare_state: Dict[str, Any]) -> Dict[str, Any]:
    performance = prepare_state.get("performance") or {}
    return {
        "matched_location_count": len(prepare_state.get("matched_locations") or []),
        "effective_location_count": len(prepare_state.get("effective_locations") or []),
        "dropped_location_count": len(prepare_state.get("dropped_locations") or []),
        "group_count": len(prepare_state.get("group_models") or []),
        "requested_dimensions": list(prepare_state.get("requested_dimensions") or []),
        "performance": {
            "load_rows_ms": performance.get("load_rows_ms"),
            "encode_ms": performance.get("encode_ms"),
            "shared_bucket_models_ms": performance.get("shared_bucket_models_ms"),
        },
    }


def _distance_summary(distance_state: Dict[str, Any], distance_hash: str, prepare_hash: str) -> Dict[str, Any]:
    matrix = np.asarray(distance_state["distance_matrix"])
    return {
        "distance_hash": distance_hash,
        "prepare_hash": prepare_hash,
        "phoneme_mode": distance_state.get("phoneme_mode"),
        "matrix_shape": [int(size) for size in matrix.shape],
        "performance": distance_state.get("performance") or {},
    }


def _result_summary(result: Dict[str, Any], result_hash: str, distance_hash: str) -> Dict[str, Any]:
    summary = result.get("summary") or {}
    return {
        "result_hash": result_hash,
        "distance_hash": distance_hash,
        "algorithm": summary.get("algorithm"),
        "phoneme_mode": summary.get("phoneme_mode"),
        "cluster_count": summary.get("cluster_count"),
        "effective_location_count": summary.get("effective_location_count"),
        "performance": (result.get("metadata") or {}).get("performance"),
    }


def _hash_preview_wrapper(snapshot: Dict[str, Any], preview: Dict[str, Any], prepare_hash: str, *, query_db: str, dialects_db: str) -> Dict[str, Any]:
    current = _now_ts()
    return {
        "artifact": {
            "stage": "preview",
            "prepare_hash": prepare_hash,
            "created_at": current,
            "updated_at": current,
            "last_accessed_at": current,
            "expires_at": current + STAGED_PREVIEW_TTL_SECONDS,
            "query_db": str(query_db),
            "dialects_db": str(dialects_db),
        },
        "snapshot": snapshot,
        "preview": preview,
    }


def _prepare_wrapper(
    prepare_hash: str,
    snapshot: Dict[str, Any],
    prepare_state: Dict[str, Any],
    *,
    query_db: str,
    dialects_db: str,
) -> Dict[str, Any]:
    current = _now_ts()
    return {
        "artifact": {
            "stage": "prepare",
            "prepare_hash": prepare_hash,
            "created_at": current,
            "updated_at": current,
            "last_accessed_at": current,
            "expires_at": current + STAGED_PREPARE_TTL_SECONDS,
            "query_db": str(query_db),
            "dialects_db": str(dialects_db),
            "summary": _prepare_summary(prepare_state),
        },
        "snapshot": snapshot,
        "payload": _prepare_json_payload(prepare_state),
    }


def _distance_wrapper(
    distance_hash: str,
    prepare_hash: str,
    distance_state: Dict[str, Any],
    *,
    query_db: str,
    dialects_db: str,
) -> Dict[str, Any]:
    current = _now_ts()
    return {
        "artifact": {
            "stage": "distance",
            "distance_hash": distance_hash,
            "prepare_hash": prepare_hash,
            "phoneme_mode": distance_state.get("phoneme_mode"),
            "created_at": current,
            "updated_at": current,
            "last_accessed_at": current,
            "expires_at": current + STAGED_DISTANCE_TTL_SECONDS,
            "query_db": str(query_db),
            "dialects_db": str(dialects_db),
            "summary": _distance_summary(distance_state, distance_hash, prepare_hash),
        },
        "payload": _distance_json_payload(distance_state),
    }


def _read_preview_bundle(prepare_hash: str) -> Dict[str, Any]:
    path = _preview_json_path(prepare_hash)
    if not path.exists():
        raise ClusterStageNotFoundError("prepare_hash 不存在，请先执行 preview")
    wrapper = _load_json(path)
    if _artifact_expired(wrapper.get("artifact")):
        path.unlink(missing_ok=True)
        raise ClusterStageNotFoundError("preview 已过期，请重新执行 preview")
    return wrapper


def _read_prepare_bundle(prepare_hash: str) -> Dict[str, Any]:
    json_path = _prepare_json_path(prepare_hash)
    npz_path = _prepare_npz_path(prepare_hash)
    if not json_path.exists() or not npz_path.exists():
        raise ClusterStageNotFoundError("prepare artifact 不存在，请先执行 prepare")
    wrapper = _load_json(json_path)
    if _artifact_expired(wrapper.get("artifact")):
        json_path.unlink(missing_ok=True)
        npz_path.unlink(missing_ok=True)
        raise ClusterStageNotFoundError("prepare artifact 已过期，请重新执行 preview/prepare")
    return {
        "artifact": wrapper["artifact"],
        "snapshot": wrapper["snapshot"],
        "prepare_state": _load_prepare_state_from_payload(wrapper["payload"], npz_path),
    }


def _read_distance_bundle(distance_hash: str) -> Dict[str, Any]:
    json_path = _distance_json_path(distance_hash)
    npy_path = _distance_npy_path(distance_hash)
    if not json_path.exists() or not npy_path.exists():
        raise ClusterStageNotFoundError("distance artifact 不存在，请先执行对应的 distance 阶段")
    wrapper = _load_json(json_path)
    if _artifact_expired(wrapper.get("artifact")):
        json_path.unlink(missing_ok=True)
        npy_path.unlink(missing_ok=True)
        raise ClusterStageNotFoundError("distance artifact 已过期，请重新执行 distance")
    return {
        "artifact": wrapper["artifact"],
        "distance_state": {
            "phoneme_mode": wrapper["payload"].get("phoneme_mode"),
            "distance_matrix": np.load(npy_path, allow_pickle=False),
            "phoneme_mode_params": wrapper["payload"].get("phoneme_mode_params") or {},
            "performance": wrapper["payload"].get("performance") or {},
        },
    }


def _ensure_result_metadata(
    result: Dict[str, Any],
    *,
    result_hash: str,
    distance_hash: str,
    prepare_hash: str,
    cache_hit: bool,
    cache_source: str,
) -> Dict[str, Any]:
    annotated = copy.deepcopy(result)
    metadata = dict(annotated.get("metadata") or {})
    current = _now_ts()
    metadata.update(
        {
            "result_hash": result_hash,
            "distance_hash": distance_hash,
            "prepare_hash": prepare_hash,
            "cache_hit": bool(cache_hit),
            "cache_source": cache_source,
            "artifact_created_at": metadata.get("artifact_created_at", current),
            "artifact_updated_at": current,
            "artifact_last_accessed_at": current,
            "artifact_expires_at": current + STAGED_RESULT_TTL_SECONDS,
        }
    )
    annotated["metadata"] = metadata
    return annotated


def _touch_preview_artifact(prepare_hash: str) -> Dict[str, Any]:
    wrapper = _read_preview_bundle(prepare_hash)
    current = _now_ts()
    wrapper["artifact"]["updated_at"] = current
    wrapper["artifact"]["last_accessed_at"] = current
    wrapper["artifact"]["expires_at"] = current + STAGED_PREVIEW_TTL_SECONDS
    _atomic_write_json(_preview_json_path(prepare_hash), wrapper)
    _touch_artifact_parent_dirs("preview")
    return wrapper


def _touch_prepare_artifact(prepare_hash: str) -> Dict[str, Any]:
    wrapper = _load_json(_prepare_json_path(prepare_hash))
    current = _now_ts()
    wrapper["artifact"]["updated_at"] = current
    wrapper["artifact"]["last_accessed_at"] = current
    wrapper["artifact"]["expires_at"] = current + STAGED_PREPARE_TTL_SECONDS
    _atomic_write_json(_prepare_json_path(prepare_hash), wrapper)
    set_cached_prepare_artifact(prepare_hash, wrapper["artifact"])
    _touch_artifact_parent_dirs("prepare")
    return wrapper["artifact"]


def _touch_distance_artifact(distance_hash: str) -> Dict[str, Any]:
    wrapper = _load_json(_distance_json_path(distance_hash))
    current = _now_ts()
    wrapper["artifact"]["updated_at"] = current
    wrapper["artifact"]["last_accessed_at"] = current
    wrapper["artifact"]["expires_at"] = current + STAGED_DISTANCE_TTL_SECONDS
    _atomic_write_json(_distance_json_path(distance_hash), wrapper)
    set_cached_distance_artifact(distance_hash, wrapper["artifact"])
    _touch_artifact_parent_dirs("distance")
    return wrapper["artifact"]


def _touch_result_artifact(result_hash: str) -> Dict[str, Any]:
    path = _result_json_path(result_hash)
    result = _load_json(path)
    metadata = dict(result.get("metadata") or {})
    current = _now_ts()
    metadata["artifact_updated_at"] = current
    metadata["artifact_last_accessed_at"] = current
    metadata["artifact_expires_at"] = current + STAGED_RESULT_TTL_SECONDS
    result["metadata"] = metadata
    _atomic_write_json(path, result)
    _touch_artifact_parent_dirs("result")
    return result


def _read_result_artifact(result_hash: str) -> Dict[str, Any]:
    path = _result_json_path(result_hash)
    if not path.exists():
        raise ClusterStageNotFoundError("result_hash 不存在或已过期")
    result = _load_json(path)
    metadata = result.get("metadata") or {}
    expires_at = float(metadata.get("artifact_expires_at", 0.0) or 0.0)
    if expires_at and expires_at <= _now_ts():
        path.unlink(missing_ok=True)
        raise ClusterStageNotFoundError("result artifact 已过期，请重新执行 cluster")
    return result


def build_staged_preview_payload(
    snapshot: Dict[str, Any],
    *,
    dialects_db: str = DIALECTS_DB_USER,
    query_db: str = QUERY_DB_USER,
) -> Dict[str, Any]:
    prepare_hash = build_cluster_prepare_hash(snapshot, dialects_db, query_db)
    preview = _build_preview(snapshot)
    lock = _get_artifact_lock(f"preview:{prepare_hash}")
    with lock:
        path = _preview_json_path(prepare_hash)
        if path.exists():
            wrapper = _touch_preview_artifact(prepare_hash)
            preview = wrapper["preview"]
        else:
            wrapper = _hash_preview_wrapper(
                snapshot,
                preview,
                prepare_hash,
                query_db=query_db,
                dialects_db=dialects_db,
            )
            _atomic_write_json(path, wrapper)
            _touch_artifact_parent_dirs("preview")
        prepare_ready = False
        if _prepare_json_path(prepare_hash).exists() and _prepare_npz_path(prepare_hash).exists():
            try:
                _read_prepare_bundle(prepare_hash)
                prepare_ready = True
            except ClusterStageNotFoundError:
                prepare_ready = False
        return {
            "prepare_hash": prepare_hash,
            "preview": preview,
            "prepare_ready": bool(prepare_ready),
            "preview_expires_at": wrapper["artifact"]["expires_at"],
        }


def materialize_prepare_artifact(
    prepare_hash: str,
    *,
    progress_callback=None,
) -> Dict[str, Any]:
    lock = _get_artifact_lock(f"prepare:{prepare_hash}")
    with lock:
        cached_meta = get_cached_prepare_artifact(prepare_hash)
        if cached_meta and not _artifact_expired(cached_meta):
            try:
                bundle = _read_prepare_bundle(prepare_hash)
                artifact_meta = _touch_prepare_artifact(prepare_hash)
                _touch_preview_artifact(prepare_hash)
                return {
                    "prepare_hash": prepare_hash,
                    "summary": artifact_meta.get("summary") or _prepare_summary(bundle["prepare_state"]),
                    "performance": (artifact_meta.get("summary") or {}).get("performance"),
                    "cache_hit": True,
                    "cache_source": "prepare",
                }
            except ClusterStageNotFoundError:
                pass

        preview_bundle = _read_preview_bundle(prepare_hash)
        snapshot = preview_bundle["snapshot"]
        dialects_db = str(preview_bundle["artifact"].get("dialects_db") or DIALECTS_DB_USER)
        query_db = str(preview_bundle["artifact"].get("query_db") or QUERY_DB_USER)

        if _prepare_json_path(prepare_hash).exists() and _prepare_npz_path(prepare_hash).exists():
            try:
                bundle = _read_prepare_bundle(prepare_hash)
                artifact_meta = _touch_prepare_artifact(prepare_hash)
                _touch_preview_artifact(prepare_hash)
                return {
                    "prepare_hash": prepare_hash,
                    "summary": artifact_meta.get("summary") or _prepare_summary(bundle["prepare_state"]),
                    "performance": (artifact_meta.get("summary") or {}).get("performance"),
                    "cache_hit": True,
                    "cache_source": "prepare",
                }
            except ClusterStageNotFoundError:
                pass

        prepare_state = build_cluster_prepare_state(
            snapshot,
            dialects_db=dialects_db,
            include_bucket_models=True,
            progress_callback=progress_callback,
        )
        wrapper = _prepare_wrapper(
            prepare_hash,
            snapshot,
            prepare_state,
            query_db=query_db,
            dialects_db=dialects_db,
        )
        _atomic_write_json(_prepare_json_path(prepare_hash), wrapper)
        _atomic_write_npz(_prepare_npz_path(prepare_hash), _prepare_arrays_payload(prepare_state))
        set_cached_prepare_artifact(prepare_hash, wrapper["artifact"])
        _touch_preview_artifact(prepare_hash)
        _touch_artifact_parent_dirs("prepare")
        return {
            "prepare_hash": prepare_hash,
            "summary": wrapper["artifact"]["summary"],
            "performance": wrapper["artifact"]["summary"].get("performance"),
            "cache_hit": False,
            "cache_source": "none",
        }


def materialize_distance_artifact(
    prepare_hash: str,
    *,
    phoneme_mode: Any,
    progress_callback=None,
) -> Dict[str, Any]:
    phoneme_mode = _normalize_phoneme_mode(phoneme_mode)
    if not phoneme_mode:
        raise ClusterStageValidationError("phoneme_mode 不能为空")
    distance_hash = build_cluster_distance_hash(prepare_hash, phoneme_mode)
    lock = _get_artifact_lock(f"distance:{distance_hash}")
    with lock:
        cached_meta = get_cached_distance_artifact(distance_hash)
        if cached_meta and not _artifact_expired(cached_meta):
            try:
                _read_distance_bundle(distance_hash)
                _touch_distance_artifact(distance_hash)
                _touch_prepare_artifact(prepare_hash)
                return {
                    "prepare_hash": prepare_hash,
                    "distance_hash": distance_hash,
                    "phoneme_mode": phoneme_mode,
                    "summary": cached_meta.get("summary"),
                    "performance": (cached_meta.get("summary") or {}).get("performance"),
                    "cache_hit": True,
                    "cache_source": "distance",
                }
            except ClusterStageNotFoundError:
                pass

        prepare_bundle = _read_prepare_bundle(prepare_hash)
        dialects_db = str(prepare_bundle["artifact"].get("dialects_db") or DIALECTS_DB_USER)
        query_db = str(prepare_bundle["artifact"].get("query_db") or QUERY_DB_USER)

        if _distance_json_path(distance_hash).exists() and _distance_npy_path(distance_hash).exists():
            try:
                bundle = _read_distance_bundle(distance_hash)
                artifact_meta = _touch_distance_artifact(distance_hash)
                _touch_prepare_artifact(prepare_hash)
                return {
                    "prepare_hash": prepare_hash,
                    "distance_hash": distance_hash,
                    "phoneme_mode": phoneme_mode,
                    "summary": artifact_meta.get("summary") or _distance_summary(bundle["distance_state"], distance_hash, prepare_hash),
                    "performance": (artifact_meta.get("summary") or {}).get("performance"),
                    "cache_hit": True,
                    "cache_source": "distance",
                }
            except ClusterStageNotFoundError:
                pass

        distance_state = build_cluster_distance_state(
            prepare_bundle["prepare_state"],
            phoneme_mode=phoneme_mode,
            dialects_db=dialects_db,
            progress_callback=progress_callback,
        )
        wrapper = _distance_wrapper(
            distance_hash,
            prepare_hash,
            distance_state,
            query_db=query_db,
            dialects_db=dialects_db,
        )
        _atomic_write_json(_distance_json_path(distance_hash), wrapper)
        _atomic_write_npy(
            _distance_npy_path(distance_hash),
            np.asarray(distance_state["distance_matrix"], dtype=np.float64),
        )
        set_cached_distance_artifact(distance_hash, wrapper["artifact"])
        _touch_prepare_artifact(prepare_hash)
        _touch_artifact_parent_dirs("distance")
        return {
            "prepare_hash": prepare_hash,
            "distance_hash": distance_hash,
            "phoneme_mode": phoneme_mode,
            "summary": wrapper["artifact"]["summary"],
            "performance": wrapper["artifact"]["summary"].get("performance"),
            "cache_hit": False,
            "cache_source": "none",
        }


def materialize_result_artifact(
    distance_hash: str,
    clustering_config: Dict[str, Any],
    *,
    progress_callback=None,
) -> Dict[str, Any]:
    distance_bundle = _read_distance_bundle(distance_hash)
    prepare_hash = str(distance_bundle["artifact"].get("prepare_hash") or "")
    if not prepare_hash:
        raise ClusterStageNotFoundError("distance artifact 缺少 prepare_hash")

    prepare_bundle = _read_prepare_bundle(prepare_hash)
    snapshot = copy.deepcopy(prepare_bundle["snapshot"])
    query_db = str(prepare_bundle["artifact"].get("query_db") or QUERY_DB_USER)
    dialects_db = str(prepare_bundle["artifact"].get("dialects_db") or DIALECTS_DB_USER)
    phoneme_mode = str(distance_bundle["distance_state"].get("phoneme_mode") or "")
    final_snapshot = copy.deepcopy(snapshot)
    final_snapshot["clustering"] = {
        **clustering_config,
        "phoneme_mode": phoneme_mode,
    }
    result_hash = build_cluster_job_hash(final_snapshot, dialects_db, query_db)
    lock = _get_artifact_lock(f"result:{result_hash}")
    with lock:
        result_path = _result_json_path(result_hash)
        if result_path.exists():
            try:
                _read_result_artifact(result_hash)
                result = _touch_result_artifact(result_hash)
                _touch_prepare_artifact(prepare_hash)
                _touch_distance_artifact(distance_hash)
                return {
                    "prepare_hash": prepare_hash,
                    "distance_hash": distance_hash,
                    "result_hash": result_hash,
                    "summary": _result_summary(result, result_hash, distance_hash),
                    "performance": (result.get("metadata") or {}).get("performance"),
                    "cache_hit": True,
                    "cache_source": "result",
                }
            except ClusterStageNotFoundError:
                pass

        cached_result = get_cached_cluster_result(result_hash)
        if cached_result is not None:
            result = _ensure_result_metadata(
                annotate_cluster_result_cache(
                    cached_result,
                    job_hash=result_hash,
                    cache_hit=True,
                    cache_source="result",
                ),
                result_hash=result_hash,
                distance_hash=distance_hash,
                prepare_hash=prepare_hash,
                cache_hit=True,
                cache_source="result",
            )
            _atomic_write_json(result_path, result)
            _touch_prepare_artifact(prepare_hash)
            _touch_distance_artifact(distance_hash)
            _touch_artifact_parent_dirs("result")
            return {
                "prepare_hash": prepare_hash,
                "distance_hash": distance_hash,
                "result_hash": result_hash,
                "summary": _result_summary(result, result_hash, distance_hash),
                "performance": (result.get("metadata") or {}).get("performance"),
                "cache_hit": True,
                "cache_source": "result",
            }

        result = build_cluster_final_result(
            final_snapshot,
            prepare_bundle["prepare_state"],
            distance_bundle["distance_state"],
            clustering_config,
            query_db=query_db,
            progress_callback=progress_callback,
        )
        result = _ensure_result_metadata(
            annotate_cluster_result_cache(
                result,
                job_hash=result_hash,
                cache_hit=False,
                cache_source="none",
            ),
            result_hash=result_hash,
            distance_hash=distance_hash,
            prepare_hash=prepare_hash,
            cache_hit=False,
            cache_source="none",
        )
        set_cached_cluster_result(result_hash, result)
        _atomic_write_json(result_path, result)
        _touch_prepare_artifact(prepare_hash)
        _touch_distance_artifact(distance_hash)
        _touch_artifact_parent_dirs("result")
        return {
            "prepare_hash": prepare_hash,
            "distance_hash": distance_hash,
            "result_hash": result_hash,
            "summary": _result_summary(result, result_hash, distance_hash),
            "performance": (result.get("metadata") or {}).get("performance"),
            "cache_hit": False,
            "cache_source": "none",
        }


def get_staged_result_by_hash(result_hash: str) -> Dict[str, Any]:
    lock = _get_artifact_lock(f"result:{result_hash}")
    with lock:
        path = _result_json_path(result_hash)
        if path.exists():
            _read_result_artifact(result_hash)
            return _touch_result_artifact(result_hash)

        cached_result = get_cached_cluster_result(result_hash)
        if cached_result is not None:
            result = annotate_cluster_result_cache(
                cached_result,
                job_hash=result_hash,
                cache_hit=True,
                cache_source="result",
            )
            result = _ensure_result_metadata(
                result,
                result_hash=result_hash,
                distance_hash=str((result.get("metadata") or {}).get("distance_hash") or ""),
                prepare_hash=str((result.get("metadata") or {}).get("prepare_hash") or ""),
                cache_hit=True,
                cache_source="result",
            )
            _atomic_write_json(path, result)
            _touch_artifact_parent_dirs("result")
            return result
    raise ClusterStageNotFoundError("result_hash 不存在或已过期")


def _build_stage_task_response(
    task_id: str,
    *,
    stage: str,
    prepare_hash: Optional[str] = None,
    distance_hash: Optional[str] = None,
    result_hash: Optional[str] = None,
    cache_hit: bool,
    cache_source: str,
) -> Dict[str, Any]:
    payload = get_task_status_payload(task_id)
    if payload is None:
        raise ClusterStageNotFoundError("任务不存在")
    return {
        "task_id": task_id,
        "stage": stage,
        "status": payload["status"],
        "progress": payload["progress"],
        "message": payload["message"],
        "summary": payload.get("summary"),
        "execution_time_ms": payload.get("execution_time_ms"),
        "performance": payload.get("performance"),
        "prepare_hash": prepare_hash,
        "distance_hash": distance_hash,
        "result_hash": result_hash,
        "cache_hit": bool(cache_hit),
        "cache_source": cache_source,
    }


def _create_cluster_task(initial_data: Dict[str, Any]) -> str:
    return task_manager.create_task(TASK_TOOL_NAME, initial_data)


def start_prepare_task(prepare_hash: str) -> Tuple[bool, Dict[str, Any]]:
    try:
        preview_bundle = _read_preview_bundle(prepare_hash)
    except ClusterStageNotFoundError as exc:
        raise ClusterStageNotFoundError(str(exc)) from exc

    preview = preview_bundle["preview"]
    cached_meta = get_cached_prepare_artifact(prepare_hash)
    if cached_meta and not _artifact_expired(cached_meta):
        try:
            materialize_prepare_artifact(prepare_hash)
            task_id = _create_cluster_task(
                {
                    "stage": "prepare",
                    "prepare_hash": prepare_hash,
                    "summary": cached_meta.get("summary") or preview,
                    "query_db": preview_bundle["artifact"].get("query_db"),
                    "dialects_db": preview_bundle["artifact"].get("dialects_db"),
                }
            )
            task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                progress=100.0,
                message="prepare 结果命中缓存",
                data={
                    "summary": cached_meta.get("summary") or preview,
                    "execution_time_ms": None,
                    "performance": (cached_meta.get("summary") or {}).get("performance"),
                },
            )
            return False, _build_stage_task_response(
                task_id,
                stage="prepare",
                prepare_hash=prepare_hash,
                cache_hit=True,
                cache_source="prepare",
            )
        except ClusterStageNotFoundError:
            pass

    inflight_task_id = get_prepare_inflight_task_id(prepare_hash)
    if inflight_task_id:
        inflight_payload = get_task_status_payload(inflight_task_id)
        if inflight_payload and inflight_payload.get("status") in {"pending", "processing"}:
            return False, _build_stage_task_response(
                inflight_task_id,
                stage="prepare",
                prepare_hash=prepare_hash,
                cache_hit=False,
                cache_source="inflight",
            )
        clear_prepare_inflight_task_id(prepare_hash, task_id=inflight_task_id)

    task_id = _create_cluster_task(
        {
            "stage": "prepare",
            "prepare_hash": prepare_hash,
            "summary": preview,
            "query_db": preview_bundle["artifact"].get("query_db"),
            "dialects_db": preview_bundle["artifact"].get("dialects_db"),
        }
    )
    set_prepare_inflight_task_id(prepare_hash, task_id)
    task_manager.update_task(
        task_id,
        status=TaskStatus.PENDING,
        progress=0.0,
        message="prepare 任务已创建",
    )
    return True, _build_stage_task_response(
        task_id,
        stage="prepare",
        prepare_hash=prepare_hash,
        cache_hit=False,
        cache_source="none",
    )


def run_prepare_task(task_id: str) -> None:
    task = task_manager.get_task(task_id)
    if not task:
        return
    prepare_hash = str((task.get("data") or {}).get("prepare_hash") or "")
    if not prepare_hash:
        task_manager.update_task(task_id, status=TaskStatus.FAILED, error="Missing prepare_hash")
        return

    started = time.perf_counter()
    try:
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=5.0,
            message="正在执行 prepare 阶段",
        )

        def _progress_callback(fraction: float, message: str, performance: Optional[Dict[str, float]] = None) -> None:
            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=round(5.0 + (91.0 * max(0.0, min(1.0, float(fraction)))), 1),
                message=message,
                data={"performance": performance or {}},
            )

        payload = materialize_prepare_artifact(prepare_hash, progress_callback=_progress_callback)
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message="prepare 阶段已完成",
            data={
                "summary": payload["summary"],
                "execution_time_ms": int((time.perf_counter() - started) * 1000),
                "performance": payload.get("performance"),
            },
        )
        clear_prepare_inflight_task_id(prepare_hash, task_id=task_id)
    except Exception as exc:
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(exc),
            message=f"prepare 阶段失败: {exc}",
        )
        clear_prepare_inflight_task_id(prepare_hash, task_id=task_id)


def start_distance_task(prepare_hash: str, phoneme_mode: Any) -> Tuple[bool, Dict[str, Any]]:
    phoneme_mode = _normalize_phoneme_mode(phoneme_mode)
    if not phoneme_mode:
        raise ClusterStageValidationError("phoneme_mode 不能为空")
    try:
        _read_prepare_bundle(prepare_hash)
    except ClusterStageNotFoundError:
        inflight_prepare = get_prepare_inflight_task_id(prepare_hash)
        if inflight_prepare:
            raise ClusterStageConflictError("prepare 阶段仍在处理中，请等待完成后再继续")
        raise

    distance_hash = build_cluster_distance_hash(prepare_hash, phoneme_mode)
    cached_meta = get_cached_distance_artifact(distance_hash)
    if cached_meta and not _artifact_expired(cached_meta):
        try:
            materialize_distance_artifact(prepare_hash, phoneme_mode=phoneme_mode)
            task_id = _create_cluster_task(
                {
                    "stage": "distance",
                    "prepare_hash": prepare_hash,
                    "distance_hash": distance_hash,
                    "summary": cached_meta.get("summary"),
                }
            )
            task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                progress=100.0,
                message=f"{phoneme_mode} distance 结果命中缓存",
                data={
                    "summary": cached_meta.get("summary"),
                    "performance": (cached_meta.get("summary") or {}).get("performance"),
                },
            )
            return False, _build_stage_task_response(
                task_id,
                stage="distance",
                prepare_hash=prepare_hash,
                distance_hash=distance_hash,
                cache_hit=True,
                cache_source="distance",
            )
        except ClusterStageNotFoundError:
            pass

    inflight_task_id = get_distance_inflight_task_id(distance_hash)
    if inflight_task_id:
        inflight_payload = get_task_status_payload(inflight_task_id)
        if inflight_payload and inflight_payload.get("status") in {"pending", "processing"}:
            return False, _build_stage_task_response(
                inflight_task_id,
                stage="distance",
                prepare_hash=prepare_hash,
                distance_hash=distance_hash,
                cache_hit=False,
                cache_source="inflight",
            )
        clear_distance_inflight_task_id(distance_hash, task_id=inflight_task_id)

    task_id = _create_cluster_task(
        {
            "stage": "distance",
            "prepare_hash": prepare_hash,
            "distance_hash": distance_hash,
            "summary": {"phoneme_mode": phoneme_mode},
        }
    )
    set_distance_inflight_task_id(distance_hash, task_id)
    task_manager.update_task(
        task_id,
        status=TaskStatus.PENDING,
        progress=0.0,
        message=f"{phoneme_mode} distance 任务已创建",
    )
    return True, _build_stage_task_response(
        task_id,
        stage="distance",
        prepare_hash=prepare_hash,
        distance_hash=distance_hash,
        cache_hit=False,
        cache_source="none",
    )


def run_distance_task(task_id: str, phoneme_mode: Any) -> None:
    task = task_manager.get_task(task_id)
    if not task:
        return
    task_data = task.get("data") or {}
    prepare_hash = str(task_data.get("prepare_hash") or "")
    distance_hash = str(task_data.get("distance_hash") or "")
    phoneme_mode = _normalize_phoneme_mode(phoneme_mode)
    started = time.perf_counter()
    try:
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=5.0,
            message=f"正在执行 {phoneme_mode} distance 阶段",
        )

        def _progress_callback(fraction: float, message: str, performance: Optional[Dict[str, float]] = None) -> None:
            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=round(5.0 + (91.0 * max(0.0, min(1.0, float(fraction)))), 1),
                message=message,
                data={"performance": performance or {}},
            )

        payload = materialize_distance_artifact(
            prepare_hash,
            phoneme_mode=phoneme_mode,
            progress_callback=_progress_callback,
        )
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message=f"{phoneme_mode} distance 阶段已完成",
            data={
                "summary": payload["summary"],
                "execution_time_ms": int((time.perf_counter() - started) * 1000),
                "performance": payload.get("performance"),
            },
        )
        clear_distance_inflight_task_id(distance_hash, task_id=task_id)
    except Exception as exc:
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(exc),
            message=f"distance 阶段失败: {exc}",
        )
        clear_distance_inflight_task_id(distance_hash, task_id=task_id)


def start_cluster_task(distance_hash: str, clustering_config: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    try:
        distance_bundle = _read_distance_bundle(distance_hash)
    except ClusterStageNotFoundError:
        inflight_distance = get_distance_inflight_task_id(distance_hash)
        if inflight_distance:
            raise ClusterStageConflictError("distance 阶段仍在处理中，请等待完成后再继续")
        raise

    prepare_hash = str(distance_bundle["artifact"].get("prepare_hash") or "")
    prepare_bundle = _read_prepare_bundle(prepare_hash)
    snapshot = copy.deepcopy(prepare_bundle["snapshot"])
    query_db = str(prepare_bundle["artifact"].get("query_db") or QUERY_DB_USER)
    dialects_db = str(prepare_bundle["artifact"].get("dialects_db") or DIALECTS_DB_USER)
    snapshot["clustering"] = {
        **clustering_config,
        "phoneme_mode": distance_bundle["distance_state"]["phoneme_mode"],
    }
    result_hash = build_cluster_job_hash(snapshot, dialects_db, query_db)

    cached_result = get_cached_cluster_result(result_hash)
    if cached_result is not None or _result_json_path(result_hash).exists():
        payload = materialize_result_artifact(distance_hash, clustering_config)
        task_id = _create_cluster_task(
            {
                "stage": "cluster",
                "prepare_hash": prepare_hash,
                "distance_hash": distance_hash,
                "result_hash": result_hash,
                "summary": payload["summary"],
                "result_path": str(_result_json_path(result_hash)),
            }
        )
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message="cluster 结果命中缓存",
            data={
                "summary": payload["summary"],
                "result_path": str(_result_json_path(result_hash)),
                "execution_time_ms": None,
                "performance": payload.get("performance"),
            },
        )
        return False, _build_stage_task_response(
            task_id,
            stage="cluster",
            prepare_hash=prepare_hash,
            distance_hash=distance_hash,
            result_hash=result_hash,
            cache_hit=True,
            cache_source="result",
        )

    inflight_task_id = get_inflight_task_id(result_hash)
    if inflight_task_id:
        inflight_payload = get_task_status_payload(inflight_task_id)
        if inflight_payload and inflight_payload.get("status") in {"pending", "processing"}:
            return False, _build_stage_task_response(
                inflight_task_id,
                stage="cluster",
                prepare_hash=prepare_hash,
                distance_hash=distance_hash,
                result_hash=result_hash,
                cache_hit=False,
                cache_source="inflight",
            )
        clear_inflight_task_id(result_hash, task_id=inflight_task_id)

    task_id = _create_cluster_task(
        {
            "stage": "cluster",
            "prepare_hash": prepare_hash,
            "distance_hash": distance_hash,
            "result_hash": result_hash,
            "summary": build_task_summary(snapshot),
        }
    )
    set_inflight_task_id(result_hash, task_id)
    task_manager.update_task(
        task_id,
        status=TaskStatus.PENDING,
        progress=0.0,
        message="cluster 任务已创建",
    )
    return True, _build_stage_task_response(
        task_id,
        stage="cluster",
        prepare_hash=prepare_hash,
        distance_hash=distance_hash,
        result_hash=result_hash,
        cache_hit=False,
        cache_source="none",
    )


def run_cluster_task(task_id: str, distance_hash: str, clustering_config: Dict[str, Any]) -> None:
    task = task_manager.get_task(task_id)
    if not task:
        return
    result_hash = str((task.get("data") or {}).get("result_hash") or "")
    started = time.perf_counter()
    try:
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=5.0,
            message="正在执行 cluster 阶段",
        )

        def _progress_callback(fraction: float, message: str, performance: Optional[Dict[str, float]] = None) -> None:
            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=round(5.0 + (91.0 * max(0.0, min(1.0, float(fraction)))), 1),
                message=message,
                data={"performance": performance or {}},
            )

        payload = materialize_result_artifact(
            distance_hash,
            clustering_config,
            progress_callback=_progress_callback,
        )
        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message="cluster 阶段已完成",
            data={
                "summary": payload["summary"],
                "result_path": str(_result_json_path(payload["result_hash"])),
                "execution_time_ms": int((time.perf_counter() - started) * 1000),
                "performance": payload.get("performance"),
            },
        )
        clear_inflight_task_id(result_hash, task_id=task_id)
    except Exception as exc:
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(exc),
            message=f"cluster 阶段失败: {exc}",
        )
        clear_inflight_task_id(result_hash, task_id=task_id)


def cleanup_cluster_stage_artifacts() -> int:
    deleted_count = 0
    current = _now_ts()
    for stage in ("preview", "prepare", "distance", "result"):
        stage_dir = _artifact_stage_dir(stage)
        if not stage_dir.exists():
            continue
        for path in stage_dir.iterdir():
            if not path.is_file() or path.name.startswith("."):
                continue
            try:
                if stage == "preview":
                    wrapper = _load_json(path)
                    if _artifact_expired(wrapper.get("artifact"), current_ts=current):
                        path.unlink(missing_ok=True)
                        deleted_count += 1
                elif stage == "prepare" and path.suffix == ".json":
                    wrapper = _load_json(path)
                    if _artifact_expired(wrapper.get("artifact"), current_ts=current):
                        path.unlink(missing_ok=True)
                        _prepare_npz_path(path.stem).unlink(missing_ok=True)
                        deleted_count += 1
                elif stage == "distance" and path.suffix == ".json":
                    wrapper = _load_json(path)
                    if _artifact_expired(wrapper.get("artifact"), current_ts=current):
                        path.unlink(missing_ok=True)
                        _distance_npy_path(path.stem).unlink(missing_ok=True)
                        deleted_count += 1
                elif stage == "result" and path.suffix == ".json":
                    result = _load_json(path)
                    metadata = result.get("metadata") or {}
                    expires_at = float(metadata.get("artifact_expires_at", 0.0))
                    if expires_at and expires_at <= current:
                        path.unlink(missing_ok=True)
                        deleted_count += 1
            except Exception:
                continue
    return deleted_count


__all__ = [
    "ClusterStageConflictError",
    "ClusterStageError",
    "ClusterStageNotFoundError",
    "ClusterStageValidationError",
    "build_staged_preview_payload",
    "cleanup_cluster_stage_artifacts",
    "get_staged_result_by_hash",
    "materialize_distance_artifact",
    "materialize_prepare_artifact",
    "materialize_result_artifact",
    "run_cluster_task",
    "run_distance_task",
    "run_prepare_task",
    "start_cluster_task",
    "start_distance_task",
    "start_prepare_task",
]
