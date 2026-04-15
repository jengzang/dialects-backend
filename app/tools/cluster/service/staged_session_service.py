"""
cluster staged session 服务。

这套服务为新的多步确认 API 提供后端状态机，核心职责是：
- 创建并维护单个 session；
- 管理 preview / prepare / distance / result 四类中间态文件；
- 负责阶段依赖、幂等复用、TTL 过期与清理；
- 复用 cluster 现有核心算法函数，不复制计算逻辑。
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from app.common.path import DIALECTS_DB_USER, QUERY_DB_USER
from app.tools.cluster.config import (
    STAGED_DISTANCE_TTL_SECONDS,
    STAGED_PREPARE_TTL_SECONDS,
    STAGED_RESULT_TTL_SECONDS,
    STAGED_SESSION_TTL_SECONDS,
    STAGED_TASK_TOOL_NAME,
)
from app.tools.cluster.service.cluster_service import (
    build_cluster_distance_state,
    build_cluster_final_result,
    build_cluster_prepare_state,
)
from app.tools.cluster.service.result_service import build_task_summary
from app.tools.file_manager import file_manager
from app.tools.task_manager import TaskStatus, task_manager


class ClusterStageError(Exception):
    """staged session 的统一基类异常。"""


class ClusterStageNotFoundError(ClusterStageError):
    """session 或 artifact 不存在。"""


class ClusterStageConflictError(ClusterStageError):
    """阶段顺序、依赖或并发状态冲突。"""


class ClusterStageValidationError(ClusterStageError):
    """阶段参数不合法。"""


_SESSION_LOCKS: Dict[str, threading.Lock] = {}
_SESSION_LOCKS_GUARD = threading.Lock()


def _get_session_lock(session_id: str) -> threading.Lock:
    with _SESSION_LOCKS_GUARD:
        lock = _SESSION_LOCKS.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _SESSION_LOCKS[session_id] = lock
        return lock


def _drop_session_lock(session_id: str) -> None:
    with _SESSION_LOCKS_GUARD:
        _SESSION_LOCKS.pop(session_id, None)


def _now_ts() -> float:
    return time.time()


def _enum_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    return value


def _normalize_phoneme_mode(phoneme_mode: Any) -> str:
    return str(_enum_value(phoneme_mode) or "")


def _stable_hash(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _session_dir(session_id: str) -> Path:
    return file_manager.get_task_dir(session_id, STAGED_TASK_TOOL_NAME)


def _session_manifest_path(session_id: str) -> Path:
    return _session_dir(session_id) / "session.json"


def _preview_path(session_id: str) -> Path:
    return _session_dir(session_id) / "preview.json"


def _prepare_json_path(session_id: str) -> Path:
    return _session_dir(session_id) / "prepare" / "prepare.json"


def _prepare_npz_path(session_id: str) -> Path:
    return _session_dir(session_id) / "prepare" / "prepare.npz"


def _distance_json_path(session_id: str, artifact_id: str) -> Path:
    return _session_dir(session_id) / "distances" / f"{artifact_id}.json"


def _distance_npy_path(session_id: str, artifact_id: str) -> Path:
    return _session_dir(session_id) / "distances" / f"{artifact_id}.npy"


def _result_json_path(session_id: str, artifact_id: str) -> Path:
    return _session_dir(session_id) / "results" / f"{artifact_id}.json"


def _relative_to_session(session_id: str, path: Path) -> str:
    return str(path.relative_to(_session_dir(session_id)))


def _resolve_session_relative_path(session_id: str, relative_path: str) -> Path:
    return _session_dir(session_id) / relative_path


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


def _task_exists(session_id: str) -> bool:
    return task_manager.get_task(session_id) is not None


def _load_session_manifest(session_id: str) -> Dict[str, Any]:
    if not _task_exists(session_id):
        raise ClusterStageNotFoundError("staged session 不存在")
    path = _session_manifest_path(session_id)
    if not path.exists():
        raise ClusterStageNotFoundError("staged session manifest 不存在")
    return _load_json(path)


def _save_session_manifest(session_id: str, manifest: Dict[str, Any]) -> None:
    manifest["updated_at"] = _now_ts()
    _atomic_write_json(_session_manifest_path(session_id), manifest)


def _normalize_artifact_summary(summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if summary is None:
        return None
    return json.loads(json.dumps(summary, ensure_ascii=False))


def _build_preview(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    location_resolution = snapshot.get("location_resolution") or {}
    groups = snapshot.get("groups") or []
    unique_chars = []
    for group in groups:
        unique_chars.extend(group.get("resolved_chars") or [])
    unique_chars = list(dict.fromkeys(unique_chars))
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
        "unique_char_count": len(unique_chars),
        "requested_dimensions": requested_dimensions,
        "estimated_pair_count": estimated_pair_count,
        "estimated_dense_matrix_mb": estimated_dense_matrix_mb,
        "available_actions": ["prepare"],
    }


def _artifact_expired(artifact: Optional[Dict[str, Any]], now_ts: Optional[float] = None) -> bool:
    if not artifact:
        return True
    if str(artifact.get("status") or "") != "completed":
        return False
    expires_at = artifact.get("expires_at")
    if expires_at is None:
        return False
    current = _now_ts() if now_ts is None else now_ts
    return float(expires_at) <= current


def _touch_session(manifest: Dict[str, Any], *, current_ts: Optional[float] = None) -> None:
    now_value = _now_ts() if current_ts is None else current_ts
    manifest["last_accessed_at"] = now_value
    manifest["expires_at"] = now_value + STAGED_SESSION_TTL_SECONDS


def _touch_artifact(
    artifact: Dict[str, Any],
    *,
    ttl_seconds: int,
    current_ts: Optional[float] = None,
) -> None:
    now_value = _now_ts() if current_ts is None else current_ts
    artifact["last_accessed_at"] = now_value
    artifact["updated_at"] = now_value
    artifact["expires_at"] = now_value + ttl_seconds


def _delete_paths(session_id: str, relative_paths: Iterable[str]) -> None:
    for relative_path in relative_paths:
        path = _resolve_session_relative_path(session_id, relative_path)
        if path.exists():
            path.unlink()


def _prepare_artifact_template(session_id: str, current_ts: float) -> Dict[str, Any]:
    return {
        "artifact_id": "prepare",
        "stage": "prepare",
        "status": "processing",
        "created_at": current_ts,
        "updated_at": current_ts,
        "last_accessed_at": current_ts,
        "expires_at": current_ts + STAGED_PREPARE_TTL_SECONDS,
        "dependency_ids": [],
        "summary": None,
        "file_paths": {
            "json": _relative_to_session(session_id, _prepare_json_path(session_id)),
            "npz": _relative_to_session(session_id, _prepare_npz_path(session_id)),
        },
    }


def _distance_artifact_id(phoneme_mode: str) -> str:
    return f"distance_{phoneme_mode}"


def _distance_artifact_template(
    session_id: str,
    *,
    artifact_id: str,
    phoneme_mode: str,
    current_ts: float,
) -> Dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "stage": "distance",
        "status": "processing",
        "created_at": current_ts,
        "updated_at": current_ts,
        "last_accessed_at": current_ts,
        "expires_at": current_ts + STAGED_DISTANCE_TTL_SECONDS,
        "dependency_ids": ["prepare"],
        "summary": {
            "phoneme_mode": phoneme_mode,
        },
        "file_paths": {
            "json": _relative_to_session(session_id, _distance_json_path(session_id, artifact_id)),
            "npy": _relative_to_session(session_id, _distance_npy_path(session_id, artifact_id)),
        },
    }


def _result_artifact_id(distance_id: str, clustering_config: Dict[str, Any]) -> str:
    result_hash = _stable_hash(
        {
            "distance_id": distance_id,
            "clustering": clustering_config,
        }
    )[:16]
    return f"result_{result_hash}"


def _result_artifact_template(
    session_id: str,
    *,
    artifact_id: str,
    distance_id: str,
    clustering_config: Dict[str, Any],
    current_ts: float,
) -> Dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "stage": "cluster",
        "status": "processing",
        "created_at": current_ts,
        "updated_at": current_ts,
        "last_accessed_at": current_ts,
        "expires_at": current_ts + STAGED_RESULT_TTL_SECONDS,
        "dependency_ids": ["prepare", distance_id],
        "summary": {
            "distance_id": distance_id,
            "clustering": clustering_config,
        },
        "file_paths": {
            "json": _relative_to_session(session_id, _result_json_path(session_id, artifact_id)),
        },
    }


def _prune_manifest_temp_files(session_id: str, manifest: Dict[str, Any]) -> None:
    referenced = {
        "session.json",
        "preview.json",
        "task_info.json",
    }
    prepare_artifact = manifest.get("prepare")
    if prepare_artifact:
        referenced.update((prepare_artifact.get("file_paths") or {}).values())
    for artifact in (manifest.get("distances") or {}).values():
        referenced.update((artifact.get("file_paths") or {}).values())
    for artifact in (manifest.get("results") or {}).values():
        referenced.update((artifact.get("file_paths") or {}).values())

    session_dir = _session_dir(session_id)
    for path in session_dir.rglob("*"):
        if not path.is_file():
            continue
        relative_path = str(path.relative_to(session_dir))
        if relative_path in referenced:
            continue
        if ".tmp" in path.name:
            path.unlink(missing_ok=True)


def _remove_prepare_and_distances(session_id: str, manifest: Dict[str, Any]) -> bool:
    changed = False
    prepare_artifact = manifest.get("prepare")
    if prepare_artifact:
        _delete_paths(session_id, (prepare_artifact.get("file_paths") or {}).values())
        manifest["prepare"] = None
        changed = True
    distances = manifest.get("distances") or {}
    for artifact in distances.values():
        _delete_paths(session_id, (artifact.get("file_paths") or {}).values())
        changed = True
    manifest["distances"] = {}
    return changed


def _expire_session_artifacts(session_id: str, manifest: Dict[str, Any]) -> bool:
    current = _now_ts()
    changed = False

    prepare_artifact = manifest.get("prepare")
    if prepare_artifact and _artifact_expired(prepare_artifact, current):
        changed = _remove_prepare_and_distances(session_id, manifest) or changed

    distances = dict(manifest.get("distances") or {})
    for artifact_id, artifact in distances.items():
        if _artifact_expired(artifact, current):
            _delete_paths(session_id, (artifact.get("file_paths") or {}).values())
            manifest["distances"].pop(artifact_id, None)
            changed = True

    results = dict(manifest.get("results") or {})
    for artifact_id, artifact in results.items():
        if _artifact_expired(artifact, current):
            _delete_paths(session_id, (artifact.get("file_paths") or {}).values())
            manifest["results"].pop(artifact_id, None)
            changed = True

    if changed:
        _prune_manifest_temp_files(session_id, manifest)
    return changed


def _find_processing_artifact(manifest: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    prepare_artifact = manifest.get("prepare")
    if prepare_artifact and str(prepare_artifact.get("status") or "") == "processing":
        return prepare_artifact

    for artifact in (manifest.get("distances") or {}).values():
        if str(artifact.get("status") or "") == "processing":
            return artifact

    for artifact in (manifest.get("results") or {}).values():
        if str(artifact.get("status") or "") == "processing":
            return artifact
    return None


def _task_status(session_id: str) -> str:
    task = task_manager.get_task(session_id)
    if not task:
        return ""
    raw_status = task.get("status")
    if hasattr(raw_status, "value"):
        return str(raw_status.value)
    return str(raw_status or "")


def _validate_no_conflicting_processing(
    manifest: Dict[str, Any],
    *,
    expected_stage: str,
    expected_artifact_id: str,
) -> None:
    processing_artifact = _find_processing_artifact(manifest)
    if not processing_artifact:
        return

    task_status = _task_status(manifest["session_id"])
    if task_status != TaskStatus.PROCESSING.value:
        # 旧 processing 标记已失效，允许后续重跑。
        processing_artifact["status"] = "failed"
        processing_artifact["updated_at"] = _now_ts()
        processing_artifact["error"] = "检测到过期的 processing 状态，已标记为 failed"
        return

    if (
        str(processing_artifact.get("stage")) == expected_stage
        and str(processing_artifact.get("artifact_id")) == expected_artifact_id
    ):
        return
    raise ClusterStageConflictError(
        f"当前 session 正在执行 {processing_artifact.get('stage')} 阶段，请等待完成后再继续"
    )


def _ensure_valid_prepare(manifest: Dict[str, Any]) -> Dict[str, Any]:
    prepare_artifact = manifest.get("prepare")
    if not prepare_artifact or str(prepare_artifact.get("status") or "") != "completed":
        raise ClusterStageConflictError("prepare 尚未完成，请先执行 prepare 阶段")
    if _artifact_expired(prepare_artifact):
        raise ClusterStageConflictError("prepare 已过期，请重新执行 prepare 阶段")
    return prepare_artifact


def _ensure_valid_distance(manifest: Dict[str, Any], distance_id: str) -> Dict[str, Any]:
    artifact = (manifest.get("distances") or {}).get(distance_id)
    if not artifact or str(artifact.get("status") or "") != "completed":
        raise ClusterStageConflictError("distance 尚未完成，请先执行对应的 distance 阶段")
    if _artifact_expired(artifact):
        raise ClusterStageConflictError("distance 已过期，请重新执行对应的 distance 阶段")
    return artifact


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


def _load_prepare_state(session_id: str, artifact: Dict[str, Any]) -> Dict[str, Any]:
    file_paths = artifact.get("file_paths") or {}
    meta = _load_json(_resolve_session_relative_path(session_id, file_paths["json"]))
    with np.load(
        _resolve_session_relative_path(session_id, file_paths["npz"]),
        allow_pickle=False,
    ) as npz_file:
        dimension_catalogs = _deserialize_dimension_catalogs(meta.get("dimension_token_catalogs") or {})
        group_models = []
        for index, group_meta in enumerate(meta.get("group_models") or []):
            group_models.append(
                _deserialize_group_model(
                    group_meta,
                    npz_file[f"group_{index}_token_matrix"],
                    npz_file[f"group_{index}_present_char_counts"],
                    dimension_catalogs,
                )
            )

        bucket_models: Dict[str, Dict[str, Any]] = {}
        for dimension, group_meta in (meta.get("bucket_models") or {}).items():
            bucket_models[dimension] = _deserialize_group_model(
                group_meta,
                npz_file[f"bucket_{dimension}_token_matrix"],
                npz_file[f"bucket_{dimension}_present_char_counts"],
                dimension_catalogs,
            )

    return {
        "matched_locations": list(meta.get("matched_locations") or []),
        "effective_locations": list(meta.get("effective_locations") or []),
        "dropped_locations": list(meta.get("dropped_locations") or []),
        "requested_dimensions": list(meta.get("requested_dimensions") or []),
        "dimension_token_catalogs": dimension_catalogs,
        "group_models": group_models,
        "bucket_models": bucket_models,
        "group_diagnostics": meta.get("group_diagnostics") or [],
        "performance": meta.get("performance") or {},
    }


def _save_prepare_artifact(
    session_id: str,
    artifact: Dict[str, Any],
    prepare_state: Dict[str, Any],
) -> None:
    file_paths = artifact.get("file_paths") or {}
    _atomic_write_json(
        _resolve_session_relative_path(session_id, file_paths["json"]),
        _prepare_json_payload(prepare_state),
    )
    _atomic_write_npz(
        _resolve_session_relative_path(session_id, file_paths["npz"]),
        _prepare_arrays_payload(prepare_state),
    )


def _distance_json_payload(distance_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "phoneme_mode": distance_state.get("phoneme_mode"),
        "phoneme_mode_params": distance_state.get("phoneme_mode_params") or {},
        "performance": distance_state.get("performance") or {},
    }


def _load_distance_state(session_id: str, artifact: Dict[str, Any]) -> Dict[str, Any]:
    file_paths = artifact.get("file_paths") or {}
    payload = _load_json(_resolve_session_relative_path(session_id, file_paths["json"]))
    distance_matrix = np.load(
        _resolve_session_relative_path(session_id, file_paths["npy"]),
        allow_pickle=False,
    )
    return {
        "phoneme_mode": payload.get("phoneme_mode"),
        "distance_matrix": distance_matrix,
        "phoneme_mode_params": payload.get("phoneme_mode_params") or {},
        "performance": payload.get("performance") or {},
    }


def _save_distance_artifact(
    session_id: str,
    artifact: Dict[str, Any],
    distance_state: Dict[str, Any],
) -> None:
    file_paths = artifact.get("file_paths") or {}
    _atomic_write_json(
        _resolve_session_relative_path(session_id, file_paths["json"]),
        _distance_json_payload(distance_state),
    )
    _atomic_write_npy(
        _resolve_session_relative_path(session_id, file_paths["npy"]),
        np.asarray(distance_state["distance_matrix"], dtype=np.float64),
    )


def _load_result_json(session_id: str, artifact: Dict[str, Any]) -> Dict[str, Any]:
    file_paths = artifact.get("file_paths") or {}
    return _load_json(_resolve_session_relative_path(session_id, file_paths["json"]))


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


def _distance_summary(distance_state: Dict[str, Any]) -> Dict[str, Any]:
    matrix = np.asarray(distance_state["distance_matrix"])
    return {
        "phoneme_mode": distance_state.get("phoneme_mode"),
        "matrix_shape": [int(size) for size in matrix.shape],
        "performance": distance_state.get("performance") or {},
    }


def _result_summary(result: Dict[str, Any], distance_id: str) -> Dict[str, Any]:
    summary = result.get("summary") or {}
    return {
        "distance_id": distance_id,
        "algorithm": summary.get("algorithm"),
        "phoneme_mode": summary.get("phoneme_mode"),
        "cluster_count": summary.get("cluster_count"),
        "effective_location_count": summary.get("effective_location_count"),
        "performance": (result.get("metadata") or {}).get("performance"),
    }


def _build_artifact_response(artifact: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "artifact_id": str(artifact.get("artifact_id")),
        "stage": str(artifact.get("stage")),
        "status": str(artifact.get("status")),
        "created_at": artifact.get("created_at"),
        "updated_at": artifact.get("updated_at"),
        "last_accessed_at": artifact.get("last_accessed_at"),
        "expires_at": artifact.get("expires_at"),
        "dependency_ids": list(artifact.get("dependency_ids") or []),
        "summary": _normalize_artifact_summary(artifact.get("summary")),
    }


def _build_available_actions(manifest: Dict[str, Any]) -> List[str]:
    if _find_processing_artifact(manifest) is not None and _task_status(manifest["session_id"]) == TaskStatus.PROCESSING.value:
        return []

    actions: List[str] = []
    prepare_artifact = manifest.get("prepare")
    if not prepare_artifact or _artifact_expired(prepare_artifact) or str(prepare_artifact.get("status")) != "completed":
        actions.append("prepare")
        return actions

    actions.append("distance")
    valid_distance_exists = any(
        str(artifact.get("status")) == "completed" and not _artifact_expired(artifact)
        for artifact in (manifest.get("distances") or {}).values()
    )
    if valid_distance_exists:
        actions.append("cluster")
    return actions


def _build_session_response(
    session_id: str,
    manifest: Dict[str, Any],
    *,
    refresh_session_access: bool,
) -> Dict[str, Any]:
    if refresh_session_access:
        _touch_session(manifest)
        _save_session_manifest(session_id, manifest)

    task = task_manager.get_task(session_id)
    if not task:
        raise ClusterStageNotFoundError("staged session 不存在")

    raw_status = task.get("status")
    status = str(raw_status.value) if hasattr(raw_status, "value") else str(raw_status or "")
    return {
        "session_id": session_id,
        "status": status,
        "progress": float(task.get("progress", 0.0)),
        "message": str(task.get("message") or ""),
        "created_at": float(manifest.get("created_at", task.get("created_at", 0.0))),
        "updated_at": float(task.get("updated_at", manifest.get("updated_at", 0.0))),
        "active_stage": manifest.get("active_stage"),
        "preview": manifest.get("preview") or {},
        "available_actions": _build_available_actions(manifest),
        "prepare": (
            _build_artifact_response(manifest["prepare"])
            if manifest.get("prepare")
            else None
        ),
        "distances": [
            _build_artifact_response(artifact)
            for artifact in sorted(
                (manifest.get("distances") or {}).values(),
                key=lambda item: float(item.get("created_at", 0.0)),
            )
        ],
        "results": [
            _build_artifact_response(artifact)
            for artifact in sorted(
                (manifest.get("results") or {}).values(),
                key=lambda item: float(item.get("created_at", 0.0)),
            )
        ],
        "execution_time_ms": (task.get("data") or {}).get("execution_time_ms"),
        "performance": (task.get("data") or {}).get("performance"),
    }


def create_staged_session(
    snapshot: Dict[str, Any],
    *,
    query_db: str = QUERY_DB_USER,
    dialects_db: str = DIALECTS_DB_USER,
) -> Dict[str, Any]:
    session_id = task_manager.create_task(
        STAGED_TASK_TOOL_NAME,
        {
            "summary": build_task_summary(snapshot),
            "query_db": query_db,
            "dialects_db": dialects_db,
        },
    )
    lock = _get_session_lock(session_id)
    with lock:
        created_at = _now_ts()
        preview = _build_preview(snapshot)
        manifest = {
            "session_id": session_id,
            "created_at": created_at,
            "updated_at": created_at,
            "last_accessed_at": created_at,
            "expires_at": created_at + STAGED_SESSION_TTL_SECONDS,
            "query_db": query_db,
            "dialects_db": dialects_db,
            "snapshot": snapshot,
            "preview": preview,
            "active_stage": None,
            "prepare": None,
            "distances": {},
            "results": {},
        }
        _atomic_write_json(_preview_path(session_id), preview)
        _save_session_manifest(session_id, manifest)
        task_manager.update_task(
            session_id,
            status="ready",
            progress=0.0,
            message="cluster staged session 已创建",
            data={
                "active_stage": None,
                "execution_time_ms": None,
                "performance": None,
            },
        )
        return _build_session_response(
            session_id,
            manifest,
            refresh_session_access=False,
        )


def get_staged_session_payload(
    session_id: str,
    *,
    refresh_session_access: bool = True,
) -> Dict[str, Any]:
    lock = _get_session_lock(session_id)
    with lock:
        manifest = _load_session_manifest(session_id)
        if _expire_session_artifacts(session_id, manifest):
            _save_session_manifest(session_id, manifest)
        return _build_session_response(
            session_id,
            manifest,
            refresh_session_access=refresh_session_access,
        )


def delete_staged_session(session_id: str) -> None:
    if not _task_exists(session_id):
        raise ClusterStageNotFoundError("staged session 不存在")
    task_manager.delete_task(session_id)
    _drop_session_lock(session_id)


def start_prepare_stage(session_id: str) -> Tuple[bool, Dict[str, Any]]:
    lock = _get_session_lock(session_id)
    with lock:
        manifest = _load_session_manifest(session_id)
        if _expire_session_artifacts(session_id, manifest):
            _save_session_manifest(session_id, manifest)

        _validate_no_conflicting_processing(
            manifest,
            expected_stage="prepare",
            expected_artifact_id="prepare",
        )
        prepare_artifact = manifest.get("prepare")
        if prepare_artifact and str(prepare_artifact.get("status")) == "completed" and not _artifact_expired(prepare_artifact):
            _touch_artifact(prepare_artifact, ttl_seconds=STAGED_PREPARE_TTL_SECONDS)
            _touch_session(manifest)
            _save_session_manifest(session_id, manifest)
            task_manager.update_task(
                session_id,
                status="ready",
                progress=100.0,
                message="prepare 已复用",
                data={
                    "active_stage": None,
                    "execution_time_ms": None,
                    "performance": prepare_artifact.get("summary", {}).get("performance"),
                },
            )
            return False, _build_session_response(session_id, manifest, refresh_session_access=False)

        current = _now_ts()
        _remove_prepare_and_distances(session_id, manifest)
        prepare_artifact = _prepare_artifact_template(session_id, current)
        manifest["prepare"] = prepare_artifact
        manifest["active_stage"] = "prepare"
        _touch_session(manifest, current_ts=current)
        _save_session_manifest(session_id, manifest)
        task_manager.update_task(
            session_id,
            status=TaskStatus.PROCESSING,
            progress=0.0,
            message="正在执行 prepare 阶段",
            data={
                "active_stage": "prepare",
                "execution_time_ms": None,
                "performance": None,
            },
        )
        return True, _build_session_response(session_id, manifest, refresh_session_access=False)


def run_prepare_stage(session_id: str) -> None:
    started = time.perf_counter()
    try:
        lock = _get_session_lock(session_id)
        with lock:
            manifest = _load_session_manifest(session_id)
            prepare_artifact = manifest.get("prepare")
            if not prepare_artifact or str(prepare_artifact.get("status")) != "processing":
                return
            snapshot = manifest["snapshot"]
            dialects_db = str(manifest.get("dialects_db") or DIALECTS_DB_USER)

        prepare_state = build_cluster_prepare_state(
            snapshot,
            dialects_db=dialects_db,
            include_bucket_models=True,
        )

        with lock:
            manifest = _load_session_manifest(session_id)
            prepare_artifact = manifest.get("prepare")
            if not prepare_artifact:
                raise ClusterStageNotFoundError("prepare artifact 不存在")
            _save_prepare_artifact(session_id, prepare_artifact, prepare_state)
            current = _now_ts()
            prepare_artifact["status"] = "completed"
            prepare_artifact["summary"] = _prepare_summary(prepare_state)
            _touch_artifact(
                prepare_artifact,
                ttl_seconds=STAGED_PREPARE_TTL_SECONDS,
                current_ts=current,
            )
            manifest["active_stage"] = None
            _touch_session(manifest, current_ts=current)
            _save_session_manifest(session_id, manifest)
            task_manager.update_task(
                session_id,
                status="ready",
                progress=100.0,
                message="prepare 阶段已完成",
                data={
                    "active_stage": None,
                    "execution_time_ms": int((time.perf_counter() - started) * 1000),
                    "performance": prepare_state.get("performance"),
                },
            )
    except Exception as exc:
        lock = _get_session_lock(session_id)
        with lock:
            try:
                manifest = _load_session_manifest(session_id)
                prepare_artifact = manifest.get("prepare")
                if prepare_artifact:
                    prepare_artifact["status"] = "failed"
                    prepare_artifact["error"] = str(exc)
                    prepare_artifact["updated_at"] = _now_ts()
                manifest["active_stage"] = None
                _touch_session(manifest)
                _save_session_manifest(session_id, manifest)
            except ClusterStageNotFoundError:
                pass
        task_manager.update_task(
            session_id,
            status=TaskStatus.FAILED,
            message=f"prepare 阶段失败: {exc}",
            error=str(exc),
            data={
                "active_stage": None,
            },
        )


def start_distance_stage(session_id: str, phoneme_mode: str) -> Tuple[bool, Dict[str, Any]]:
    phoneme_mode = _normalize_phoneme_mode(phoneme_mode)
    artifact_id = _distance_artifact_id(phoneme_mode)
    lock = _get_session_lock(session_id)
    with lock:
        manifest = _load_session_manifest(session_id)
        if _expire_session_artifacts(session_id, manifest):
            _save_session_manifest(session_id, manifest)

        _ensure_valid_prepare(manifest)
        _validate_no_conflicting_processing(
            manifest,
            expected_stage="distance",
            expected_artifact_id=artifact_id,
        )

        distance_artifact = (manifest.get("distances") or {}).get(artifact_id)
        if distance_artifact and str(distance_artifact.get("status")) == "completed" and not _artifact_expired(distance_artifact):
            _touch_artifact(manifest["prepare"], ttl_seconds=STAGED_PREPARE_TTL_SECONDS)
            _touch_artifact(distance_artifact, ttl_seconds=STAGED_DISTANCE_TTL_SECONDS)
            _touch_session(manifest)
            _save_session_manifest(session_id, manifest)
            task_manager.update_task(
                session_id,
                status="ready",
                progress=100.0,
                message=f"{phoneme_mode} distance 已复用",
                data={
                    "active_stage": None,
                    "execution_time_ms": None,
                    "performance": distance_artifact.get("summary", {}).get("performance"),
                },
            )
            return False, _build_session_response(session_id, manifest, refresh_session_access=False)

        current = _now_ts()
        distance_artifact = _distance_artifact_template(
            session_id,
            artifact_id=artifact_id,
            phoneme_mode=phoneme_mode,
            current_ts=current,
        )
        manifest.setdefault("distances", {})[artifact_id] = distance_artifact
        manifest["active_stage"] = "distance"
        _touch_session(manifest, current_ts=current)
        _save_session_manifest(session_id, manifest)
        task_manager.update_task(
            session_id,
            status=TaskStatus.PROCESSING,
            progress=0.0,
            message=f"正在执行 {phoneme_mode} distance 阶段",
            data={
                "active_stage": "distance",
                "execution_time_ms": None,
                "performance": None,
            },
        )
        return True, _build_session_response(session_id, manifest, refresh_session_access=False)


def run_distance_stage(session_id: str, phoneme_mode: str) -> None:
    phoneme_mode = _normalize_phoneme_mode(phoneme_mode)
    artifact_id = _distance_artifact_id(phoneme_mode)
    started = time.perf_counter()
    try:
        lock = _get_session_lock(session_id)
        with lock:
            manifest = _load_session_manifest(session_id)
            prepare_artifact = _ensure_valid_prepare(manifest)
            distance_artifact = (manifest.get("distances") or {}).get(artifact_id)
            if not distance_artifact or str(distance_artifact.get("status")) != "processing":
                return
            dialects_db = str(manifest.get("dialects_db") or DIALECTS_DB_USER)
            prepare_state = _load_prepare_state(session_id, prepare_artifact)

        distance_state = build_cluster_distance_state(
            prepare_state,
            phoneme_mode=phoneme_mode,
            dialects_db=dialects_db,
        )

        with lock:
            manifest = _load_session_manifest(session_id)
            prepare_artifact = _ensure_valid_prepare(manifest)
            distance_artifact = (manifest.get("distances") or {}).get(artifact_id)
            if not distance_artifact:
                raise ClusterStageNotFoundError("distance artifact 不存在")
            _save_distance_artifact(session_id, distance_artifact, distance_state)
            current = _now_ts()
            _touch_artifact(prepare_artifact, ttl_seconds=STAGED_PREPARE_TTL_SECONDS, current_ts=current)
            distance_artifact["status"] = "completed"
            distance_artifact["summary"] = _distance_summary(distance_state)
            _touch_artifact(
                distance_artifact,
                ttl_seconds=STAGED_DISTANCE_TTL_SECONDS,
                current_ts=current,
            )
            manifest["active_stage"] = None
            _touch_session(manifest, current_ts=current)
            _save_session_manifest(session_id, manifest)
            task_manager.update_task(
                session_id,
                status="ready",
                progress=100.0,
                message=f"{phoneme_mode} distance 阶段已完成",
                data={
                    "active_stage": None,
                    "execution_time_ms": int((time.perf_counter() - started) * 1000),
                    "performance": distance_state.get("performance"),
                },
            )
    except Exception as exc:
        lock = _get_session_lock(session_id)
        with lock:
            try:
                manifest = _load_session_manifest(session_id)
                distance_artifact = (manifest.get("distances") or {}).get(artifact_id)
                if distance_artifact:
                    distance_artifact["status"] = "failed"
                    distance_artifact["error"] = str(exc)
                    distance_artifact["updated_at"] = _now_ts()
                manifest["active_stage"] = None
                _touch_session(manifest)
                _save_session_manifest(session_id, manifest)
            except ClusterStageNotFoundError:
                pass
        task_manager.update_task(
            session_id,
            status=TaskStatus.FAILED,
            message=f"distance 阶段失败: {exc}",
            error=str(exc),
            data={
                "active_stage": None,
            },
        )


def start_cluster_stage(
    session_id: str,
    *,
    distance_id: str,
    clustering_config: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any], str]:
    if not distance_id:
        raise ClusterStageValidationError("distance_id 不能为空")

    artifact_id = _result_artifact_id(distance_id, clustering_config)
    lock = _get_session_lock(session_id)
    with lock:
        manifest = _load_session_manifest(session_id)
        if _expire_session_artifacts(session_id, manifest):
            _save_session_manifest(session_id, manifest)

        _ensure_valid_prepare(manifest)
        _ensure_valid_distance(manifest, distance_id)
        _validate_no_conflicting_processing(
            manifest,
            expected_stage="cluster",
            expected_artifact_id=artifact_id,
        )

        result_artifact = (manifest.get("results") or {}).get(artifact_id)
        if result_artifact and str(result_artifact.get("status")) == "completed" and not _artifact_expired(result_artifact):
            _touch_artifact(manifest["prepare"], ttl_seconds=STAGED_PREPARE_TTL_SECONDS)
            _touch_artifact(manifest["distances"][distance_id], ttl_seconds=STAGED_DISTANCE_TTL_SECONDS)
            _touch_artifact(result_artifact, ttl_seconds=STAGED_RESULT_TTL_SECONDS)
            _touch_session(manifest)
            _save_session_manifest(session_id, manifest)
            task_manager.update_task(
                session_id,
                status="ready",
                progress=100.0,
                message=f"{artifact_id} 已复用",
                data={
                    "active_stage": None,
                    "execution_time_ms": None,
                    "performance": result_artifact.get("summary", {}).get("performance"),
                },
            )
            return False, _build_session_response(session_id, manifest, refresh_session_access=False), artifact_id

        current = _now_ts()
        result_artifact = _result_artifact_template(
            session_id,
            artifact_id=artifact_id,
            distance_id=distance_id,
            clustering_config=clustering_config,
            current_ts=current,
        )
        manifest.setdefault("results", {})[artifact_id] = result_artifact
        manifest["active_stage"] = "cluster"
        _touch_session(manifest, current_ts=current)
        _save_session_manifest(session_id, manifest)
        task_manager.update_task(
            session_id,
            status=TaskStatus.PROCESSING,
            progress=0.0,
            message=f"正在执行 cluster 阶段: {artifact_id}",
            data={
                "active_stage": "cluster",
                "execution_time_ms": None,
                "performance": None,
            },
        )
        return True, _build_session_response(session_id, manifest, refresh_session_access=False), artifact_id


def run_cluster_stage(
    session_id: str,
    *,
    distance_id: str,
    result_id: str,
    clustering_config: Dict[str, Any],
) -> None:
    try:
        lock = _get_session_lock(session_id)
        with lock:
            manifest = _load_session_manifest(session_id)
            prepare_artifact = _ensure_valid_prepare(manifest)
            distance_artifact = _ensure_valid_distance(manifest, distance_id)
            result_artifact = (manifest.get("results") or {}).get(result_id)
            if not result_artifact or str(result_artifact.get("status")) != "processing":
                return
            snapshot = manifest["snapshot"]
            query_db = str(manifest.get("query_db") or QUERY_DB_USER)
            prepare_state = _load_prepare_state(session_id, prepare_artifact)
            distance_state = _load_distance_state(session_id, distance_artifact)

        result = build_cluster_final_result(
            snapshot,
            prepare_state,
            distance_state,
            clustering_config,
            query_db=query_db,
        )

        with lock:
            manifest = _load_session_manifest(session_id)
            prepare_artifact = _ensure_valid_prepare(manifest)
            distance_artifact = _ensure_valid_distance(manifest, distance_id)
            result_artifact = (manifest.get("results") or {}).get(result_id)
            if not result_artifact:
                raise ClusterStageNotFoundError("result artifact 不存在")
            file_paths = result_artifact.get("file_paths") or {}
            _atomic_write_json(
                _resolve_session_relative_path(session_id, file_paths["json"]),
                result,
            )
            current = _now_ts()
            _touch_artifact(prepare_artifact, ttl_seconds=STAGED_PREPARE_TTL_SECONDS, current_ts=current)
            _touch_artifact(distance_artifact, ttl_seconds=STAGED_DISTANCE_TTL_SECONDS, current_ts=current)
            result_artifact["status"] = "completed"
            result_artifact["summary"] = _result_summary(result, distance_id)
            _touch_artifact(
                result_artifact,
                ttl_seconds=STAGED_RESULT_TTL_SECONDS,
                current_ts=current,
            )
            manifest["active_stage"] = None
            _touch_session(manifest, current_ts=current)
            _save_session_manifest(session_id, manifest)
            task_manager.update_task(
                session_id,
                status="ready",
                progress=100.0,
                message=f"cluster 阶段已完成: {result_id}",
                data={
                    "active_stage": None,
                    "execution_time_ms": (result.get("metadata") or {}).get("execution_time_ms"),
                    "performance": (result.get("metadata") or {}).get("performance"),
                },
            )
    except Exception as exc:
        lock = _get_session_lock(session_id)
        with lock:
            try:
                manifest = _load_session_manifest(session_id)
                result_artifact = (manifest.get("results") or {}).get(result_id)
                if result_artifact:
                    result_artifact["status"] = "failed"
                    result_artifact["error"] = str(exc)
                    result_artifact["updated_at"] = _now_ts()
                manifest["active_stage"] = None
                _touch_session(manifest)
                _save_session_manifest(session_id, manifest)
            except ClusterStageNotFoundError:
                pass
        task_manager.update_task(
            session_id,
            status=TaskStatus.FAILED,
            message=f"cluster 阶段失败: {exc}",
            error=str(exc),
            data={
                "active_stage": None,
            },
        )


def get_staged_cluster_result(session_id: str, result_id: str) -> Dict[str, Any]:
    lock = _get_session_lock(session_id)
    with lock:
        manifest = _load_session_manifest(session_id)
        if _expire_session_artifacts(session_id, manifest):
            _save_session_manifest(session_id, manifest)
        artifact = (manifest.get("results") or {}).get(result_id)
        if not artifact:
            raise ClusterStageNotFoundError("result artifact 不存在")
        if str(artifact.get("status")) != "completed":
            raise ClusterStageConflictError("结果尚未完成，暂时无法读取")
        if _artifact_expired(artifact):
            raise ClusterStageNotFoundError("result artifact 已过期")
        _touch_artifact(artifact, ttl_seconds=STAGED_RESULT_TTL_SECONDS)
        _touch_session(manifest)
        _save_session_manifest(session_id, manifest)
        return _load_result_json(session_id, artifact)


def cleanup_cluster_stage_sessions() -> int:
    tool_dir = file_manager.get_tool_dir(STAGED_TASK_TOOL_NAME)
    if not tool_dir.exists():
        return 0

    deleted_count = 0
    current = _now_ts()
    for session_dir in tool_dir.iterdir():
        if not session_dir.is_dir():
            continue

        session_id = session_dir.name
        lock = _get_session_lock(session_id)
        with lock:
            manifest_path = session_dir / "session.json"
            task_info_path = session_dir / "task_info.json"
            if not manifest_path.exists():
                if not task_info_path.exists():
                    file_manager.delete_task_files(session_id, STAGED_TASK_TOOL_NAME)
                    _drop_session_lock(session_id)
                    deleted_count += 1
                continue

            try:
                manifest = _load_json(manifest_path)
            except Exception:
                file_manager.delete_task_files(session_id, STAGED_TASK_TOOL_NAME)
                _drop_session_lock(session_id)
                deleted_count += 1
                continue

            task_status = _task_status(session_id)
            session_expired = float(manifest.get("expires_at", 0.0)) <= current
            if session_expired and task_status != TaskStatus.PROCESSING.value:
                task_manager.delete_task(session_id)
                _drop_session_lock(session_id)
                deleted_count += 1
                continue

            if _expire_session_artifacts(session_id, manifest):
                _save_session_manifest(session_id, manifest)

    return deleted_count


__all__ = [
    "ClusterStageConflictError",
    "ClusterStageError",
    "ClusterStageNotFoundError",
    "ClusterStageValidationError",
    "cleanup_cluster_stage_sessions",
    "create_staged_session",
    "delete_staged_session",
    "get_staged_cluster_result",
    "get_staged_session_payload",
    "run_cluster_stage",
    "run_distance_stage",
    "run_prepare_stage",
    "start_cluster_stage",
    "start_distance_stage",
    "start_prepare_stage",
]
