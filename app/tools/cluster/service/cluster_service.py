"""
cluster 主服务编排层。

这是整个聚类工具的核心门面：
- `build_cluster_result()` 负责把 snapshot 走完整条计算链；
- `run_cluster_job()` 负责与任务系统、缓存系统衔接。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from app.common.path import DIALECTS_DB_USER, QUERY_DB_USER
from app.tools.cluster.config import DEFAULT_PHONEME_MODE
from app.tools.cluster.service.cache_service import (
    annotate_cluster_result_cache,
    build_cluster_job_hash,
    clear_inflight_task_id,
    get_cached_cluster_result,
    set_cached_cluster_result,
)
from app.tools.cluster.service.distance_service import (
    build_dimension_bucket_models,
    build_dimension_token_catalogs,
    build_group_model,
    build_total_distance_matrix,
)
from app.tools.cluster.service.loader_service import (
    load_dialect_rows,
    load_dimension_inventory_profiles,
    load_location_details,
)
from app.tools.cluster.service.pipeline_service import (
    choose_execution_space,
    classical_mds,
    compute_metrics,
    prepare_feature_space,
    run_agglomerative,
    run_dbscan,
    run_gmm,
    run_kmeans,
)
from app.tools.cluster.service.resolver_service import (
    resolve_cluster_groups,
    resolve_cluster_job_snapshot,
)
from app.tools.cluster.service.result_service import (
    build_assignments,
    build_group_diagnostics,
    build_result_payload,
    build_task_summary,
    collect_cluster_warnings,
)
from app.tools.cluster.service.task_service import (
    get_cluster_result,
    get_task_status_payload,
    is_cancel_requested,
    write_result,
)
from app.tools.cluster.utils import dedupe
from app.tools.task_manager import TaskStatus, task_manager

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[float, str, Optional[Dict[str, float]]], None]


def _emit_progress(
    progress_callback: Optional[ProgressCallback],
    fraction: float,
    message: str,
    performance: Optional[Dict[str, float]] = None,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        max(0.0, min(1.0, float(fraction))),
        message,
        dict(performance or {}) or None,
    )


def _make_substage_progress_callback(
    progress_callback: Optional[ProgressCallback],
    start_fraction: float,
    end_fraction: float,
) -> Optional[ProgressCallback]:
    if progress_callback is None:
        return None

    def _callback(
        fraction: float,
        message: str,
        performance: Optional[Dict[str, float]] = None,
    ) -> None:
        normalized = max(0.0, min(1.0, float(fraction)))
        mapped_fraction = start_fraction + ((end_fraction - start_fraction) * normalized)
        _emit_progress(progress_callback, mapped_fraction, message, performance)

    return _callback


def _slice_group_model_to_locations(
    group_model: Dict[str, Any],
    source_locations: List[str],
    target_locations: List[str],
) -> Dict[str, Any]:
    if source_locations == target_locations:
        return group_model

    index_by_location = {location: index for index, location in enumerate(source_locations)}
    indices = np.asarray(
        [index_by_location[location] for location in target_locations],
        dtype=np.int32,
    )
    token_matrix = np.asarray(group_model["token_matrix"][indices], dtype=np.int32)
    present_char_counts = np.asarray(group_model["present_char_counts"][indices], dtype=np.int32)
    char_count = int(group_model.get("char_count", token_matrix.shape[1]))

    locations: Dict[str, Dict[str, Any]] = {}
    for index, location in enumerate(target_locations):
        present_char_count = int(present_char_counts[index])
        locations[location] = {
            "token_ids": token_matrix[index],
            "present_char_count": present_char_count,
            "coverage": (
                float(present_char_count / char_count)
                if char_count
                else 0.0
            ),
        }

    sliced = dict(group_model)
    sliced["locations"] = locations
    sliced["token_matrix"] = token_matrix
    sliced["present_char_counts"] = present_char_counts
    sliced["effective_locations"] = list(target_locations)
    return sliced


def build_cluster_prepare_state(
    snapshot: Dict[str, Any],
    dialects_db: str = DIALECTS_DB_USER,
    include_bucket_models: bool = False,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """执行 cluster 的 prepare 阶段：读取方言数据并编码成 token 矩阵。"""
    groups = snapshot["groups"]
    matched_locations = snapshot["location_resolution"]["matched_locations"]
    all_chars = dedupe(char for group in groups for char in group["resolved_chars"])
    requested_dimensions = sorted(
        {group["compare_dimension"] for group in groups if group.get("compare_dimension")}
    )
    performance: Dict[str, float] = {}

    _emit_progress(progress_callback, 0.05, "正在读取方言数据", performance)
    load_start = time.perf_counter()
    dialect_data = load_dialect_rows(
        matched_locations,
        all_chars,
        dialects_db,
        requested_dimensions=requested_dimensions,
    )
    performance["load_rows_ms"] = round((time.perf_counter() - load_start) * 1000.0, 3)

    _emit_progress(progress_callback, 0.42, "正在编码聚类输入", performance)
    encode_start = time.perf_counter()
    dimension_token_catalogs = build_dimension_token_catalogs(groups, dialect_data)
    full_group_models = [
        build_group_model(
            group,
            matched_locations,
            dialect_data,
            dimension_token_catalogs[group["compare_dimension"]],
        )
        for group in groups
    ]
    effective_locations = [
        location
        for location in matched_locations
        if any(
            group["locations"][location]["present_char_count"] > 0 for group in full_group_models
        )
    ]
    if len(effective_locations) < 2:
        raise ValueError("有效地点不足 2 个，无法执行聚类")

    group_diagnostics = build_group_diagnostics(
        full_group_models,
        matched_locations,
        effective_locations,
    )
    performance["encode_ms"] = round((time.perf_counter() - encode_start) * 1000.0, 3)
    dropped_locations = [
        location for location in matched_locations if location not in effective_locations
    ]
    group_models = [
        _slice_group_model_to_locations(group_model, matched_locations, effective_locations)
        for group_model in full_group_models
    ]

    bucket_models: Dict[str, Dict[str, Any]] = {}
    shared_bucket_models_ms = 0.0
    if include_bucket_models:
        _emit_progress(progress_callback, 0.75, "正在构建 shared identity 共享模型", performance)
        bucket_start = time.perf_counter()
        bucket_models = build_dimension_bucket_models(
            groups,
            effective_locations,
            dialect_data,
            dimension_token_catalogs,
        )
        shared_bucket_models_ms = round((time.perf_counter() - bucket_start) * 1000.0, 3)

    result = {
        "matched_locations": list(matched_locations),
        "effective_locations": list(effective_locations),
        "dropped_locations": list(dropped_locations),
        "requested_dimensions": list(requested_dimensions),
        "dimension_token_catalogs": dimension_token_catalogs,
        "group_models": group_models,
        "group_diagnostics": group_diagnostics,
        "bucket_models": bucket_models,
        "performance": {
            **performance,
            "shared_bucket_models_ms": shared_bucket_models_ms,
        },
    }
    _emit_progress(progress_callback, 0.98, "prepare 阶段即将完成", result["performance"])
    return result


def build_cluster_distance_state(
    prepare_state: Dict[str, Any],
    phoneme_mode: str,
    dialects_db: str = DIALECTS_DB_USER,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """执行 cluster 的 distance 阶段：生成指定 phoneme_mode 的距离矩阵。"""
    effective_locations = list(prepare_state["effective_locations"])
    group_models = prepare_state["group_models"]
    performance: Dict[str, float] = {
        "inventory_profiles_ms": 0.0,
        "bucket_models_ms": 0.0,
    }

    inventory_profiles: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
    if phoneme_mode == "anchored_inventory":
        _emit_progress(progress_callback, 0.12, "正在构建 anchored inventory 库存画像", performance)
        inventory_profiles_start = time.perf_counter()
        inventory_profiles = load_dimension_inventory_profiles(
            effective_locations,
            [group["compare_dimension"] for group in group_models],
            dialects_db,
        )
        performance["inventory_profiles_ms"] = round(
            (time.perf_counter() - inventory_profiles_start) * 1000.0,
            3,
        )

    bucket_models: Dict[str, Dict[str, Any]] = {}
    if phoneme_mode == "shared_request_identity":
        _emit_progress(progress_callback, 0.12, "正在准备 shared identity 共享模型", performance)
        bucket_models = prepare_state.get("bucket_models") or {}
        if not bucket_models:
            raise ValueError("prepare 阶段缺少 shared_request_identity 所需的 bucket models")
        performance["bucket_models_ms"] = round(
            float((prepare_state.get("performance") or {}).get("shared_bucket_models_ms", 0.0)),
            3,
        )

    if phoneme_mode == "intra_group":
        _emit_progress(progress_callback, 0.12, "正在准备音系距离矩阵输入", performance)
    _emit_progress(progress_callback, 0.38, "正在计算地点两两音系距离", performance)
    distance_start = time.perf_counter()
    distance_matrix, phoneme_mode_params = build_total_distance_matrix(
        group_models=group_models,
        locations=effective_locations,
        phoneme_mode=phoneme_mode,
        inventory_profiles=inventory_profiles,
        bucket_models=bucket_models,
    )
    performance["distance_matrix_ms"] = round(
        (time.perf_counter() - distance_start) * 1000.0,
        3,
    )

    result = {
        "phoneme_mode": phoneme_mode,
        "distance_matrix": distance_matrix,
        "phoneme_mode_params": phoneme_mode_params,
        "performance": performance,
    }
    _emit_progress(progress_callback, 0.98, "distance 阶段即将完成", performance)
    return result


def build_cluster_final_result(
    snapshot: Dict[str, Any],
    prepare_state: Dict[str, Any],
    distance_state: Dict[str, Any],
    clustering_config: Dict[str, Any],
    query_db: str = QUERY_DB_USER,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """执行 cluster 的最后一步：从距离矩阵生成最终聚类结果 JSON。"""
    performance = dict(snapshot.get("performance") or {})
    prepare_performance = dict(prepare_state.get("performance") or {})
    distance_performance = dict(distance_state.get("performance") or {})
    performance.update(
        {
            "load_rows_ms": round(float(prepare_performance.get("load_rows_ms", 0.0)), 3),
            "encode_ms": round(float(prepare_performance.get("encode_ms", 0.0)), 3),
            "inventory_profiles_ms": round(float(distance_performance.get("inventory_profiles_ms", 0.0)), 3),
            "bucket_models_ms": round(float(distance_performance.get("bucket_models_ms", 0.0)), 3),
            "distance_matrix_ms": round(float(distance_performance.get("distance_matrix_ms", 0.0)), 3),
        }
    )

    matched_locations = snapshot["location_resolution"]["matched_locations"]
    effective_locations = list(prepare_state["effective_locations"])
    dropped_locations = list(prepare_state["dropped_locations"])
    group_diagnostics = prepare_state["group_diagnostics"]
    phoneme_mode = distance_state["phoneme_mode"]
    legacy_metric_mode = (snapshot.get("clustering") or {}).get("metric_mode")
    distance_matrix = distance_state["distance_matrix"]
    algorithm = clustering_config["algorithm"]
    execution_space = choose_execution_space(algorithm=algorithm)

    _emit_progress(progress_callback, 0.10, "正在读取地点展示信息", performance)
    location_detail_start = time.perf_counter()
    location_details = load_location_details(matched_locations, query_db)
    performance["location_details_ms"] = round(
        (time.perf_counter() - location_detail_start) * 1000.0,
        3,
    )

    labels: np.ndarray
    assignments: List[Dict[str, Any]]
    metrics_matrix: Optional[np.ndarray] = None

    _emit_progress(progress_callback, 0.42, "正在执行聚类", performance)
    cluster_start = time.perf_counter()
    if algorithm == "agglomerative":
        n_clusters = int(clustering_config["n_clusters"])
        if n_clusters > len(effective_locations):
            raise ValueError("n_clusters 不能大于有效地点数")
        labels = run_agglomerative(distance_matrix, n_clusters, clustering_config.get("linkage", "average"))
        assignments = build_assignments(effective_locations, labels, location_details)
    elif algorithm == "dbscan":
        labels = run_dbscan(
            distance_matrix,
            eps=float(clustering_config.get("eps", 0.5)),
            min_samples=int(clustering_config.get("min_samples", 5)),
        )
        assignments = build_assignments(effective_locations, labels, location_details)
    elif algorithm == "kmeans":
        n_clusters = int(clustering_config["n_clusters"])
        if n_clusters > len(effective_locations):
            raise ValueError("n_clusters 不能大于有效地点数")
        metrics_matrix = prepare_feature_space(
            classical_mds(
                distance_matrix,
                n_components=min(8, max(len(effective_locations) - 1, 1)),
            )
        )
        labels, centroid_distance = run_kmeans(
            metrics_matrix,
            n_clusters=n_clusters,
            random_state=int(clustering_config.get("random_state", 42)),
        )
        assignments = build_assignments(
            effective_locations,
            labels,
            location_details,
            extra_values=centroid_distance,
            extra_key="distance_to_centroid",
        )
    elif algorithm == "gmm":
        n_clusters = int(clustering_config["n_clusters"])
        if n_clusters > len(effective_locations):
            raise ValueError("n_clusters 不能大于有效地点数")
        metrics_matrix = prepare_feature_space(
            classical_mds(
                distance_matrix,
                n_components=min(8, max(len(effective_locations) - 1, 1)),
            )
        )
        labels, membership = run_gmm(
            metrics_matrix,
            n_clusters=n_clusters,
            random_state=int(clustering_config.get("random_state", 42)),
        )
        assignments = build_assignments(
            effective_locations,
            labels,
            location_details,
            extra_values=membership,
            extra_key="membership_score",
        )
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    metrics = compute_metrics(
        labels=labels,
        execution_matrix=metrics_matrix,
        distance_matrix=distance_matrix if algorithm in {"agglomerative", "dbscan"} else None,
    )
    warnings = collect_cluster_warnings(
        legacy_metric_mode=legacy_metric_mode,
        phoneme_mode=phoneme_mode,
        filtered_special_locations=snapshot["location_resolution"].get("filtered_special_locations") or [],
        dropped_locations=dropped_locations,
        group_diagnostics=group_diagnostics,
    )
    performance["cluster_ms"] = round((time.perf_counter() - cluster_start) * 1000.0, 3)
    _emit_progress(progress_callback, 0.88, "正在整理聚类结果", performance)
    execution_time_ms = int(
        round(
            sum(
                float(value)
                for value in performance.values()
                if isinstance(value, (int, float))
            )
        )
    )

    result = build_result_payload(
        snapshot=snapshot,
        algorithm=algorithm,
        phoneme_mode=phoneme_mode,
        legacy_metric_mode=legacy_metric_mode,
        matched_locations=matched_locations,
        effective_locations=effective_locations,
        dropped_locations=dropped_locations,
        labels=labels,
        assignments=assignments,
        group_diagnostics=group_diagnostics,
        metrics=metrics,
        execution_space=execution_space,
        execution_time_ms=execution_time_ms,
        performance=performance,
        phoneme_mode_params=distance_state["phoneme_mode_params"],
        warnings=warnings,
        location_details=location_details,
    )
    _emit_progress(progress_callback, 0.98, "cluster 阶段即将完成", performance)
    return result


def build_cluster_result(
    snapshot: Dict[str, Any],
    dialects_db: str = DIALECTS_DB_USER,
    query_db: str = QUERY_DB_USER,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """
    根据 snapshot 真正执行一次聚类，并返回完整结果。

    旧 one-shot API 仍然走同样的入口，只是内部改成串联
    prepare -> distance -> final 三个纯阶段函数。
    """
    start_time = time.perf_counter()
    clustering = snapshot["clustering"]
    phoneme_mode = clustering.get("phoneme_mode", DEFAULT_PHONEME_MODE)
    prepare_state = build_cluster_prepare_state(
        snapshot,
        dialects_db=dialects_db,
        include_bucket_models=(phoneme_mode == "shared_request_identity"),
        progress_callback=_make_substage_progress_callback(progress_callback, 0.0, 0.56),
    )
    distance_state = build_cluster_distance_state(
        prepare_state,
        phoneme_mode=phoneme_mode,
        dialects_db=dialects_db,
        progress_callback=_make_substage_progress_callback(progress_callback, 0.56, 0.90),
    )
    result = build_cluster_final_result(
        snapshot,
        prepare_state,
        distance_state,
        clustering,
        query_db=query_db,
        progress_callback=_make_substage_progress_callback(progress_callback, 0.90, 0.98),
    )
    metadata = dict(result.get("metadata") or {})
    metadata["execution_time_ms"] = int((time.perf_counter() - start_time) * 1000)
    result["metadata"] = metadata
    return result


def run_cluster_job(
    task_id: str,
    dialects_db: str = DIALECTS_DB_USER,
    query_db: str = QUERY_DB_USER,
):
    """
    后台任务执行入口。

    它负责：
    - 检查 snapshot 是否存在；
    - 再次尝试命中结果缓存；
    - 调 `build_cluster_result()`；
    - 写入结果文件和任务状态；
    - 在成功、失败、取消三种情况下都清理 inflight 标记。
    """
    task = task_manager.get_task(task_id)
    if not task:
        return

    snapshot = (task.get("data") or {}).get("snapshot")
    if not snapshot:
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error="Missing cluster snapshot",
            message="缺少聚类任务快照",
        )
        return
    task_data = task.get("data") or {}
    job_hash = task_data.get("job_hash") or build_cluster_job_hash(
        snapshot,
        dialects_db,
        query_db,
    )

    try:
        if is_cancel_requested(task_id):
            clear_inflight_task_id(job_hash, task_id=task_id)
            return

        cached_result = get_cached_cluster_result(job_hash)
        if cached_result is not None:
            result = annotate_cluster_result_cache(
                cached_result,
                job_hash=job_hash,
                cache_hit=True,
                cache_source="result",
            )
            result_path = write_result(task_id, result)
            task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                progress=100.0,
                message="聚类结果命中缓存",
                data={
                    "result_path": str(result_path),
                    "summary": build_task_summary(snapshot, result=result),
                    "job_hash": job_hash,
                    "execution_time_ms": (result.get("metadata") or {}).get("execution_time_ms"),
                    "performance": (result.get("metadata") or {}).get("performance"),
                },
            )
            clear_inflight_task_id(job_hash, task_id=task_id)
            return

        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=5.0,
            message="正在准备聚类计算",
        )

        def _progress_callback(
            fraction: float,
            message: str,
            performance: Optional[Dict[str, float]] = None,
        ) -> None:
            data: Dict[str, Any] = {}
            if performance is not None:
                data["performance"] = performance
            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=round(5.0 + (91.0 * max(0.0, min(1.0, float(fraction)))), 1),
                message=message,
                data=data,
            )

        result = build_cluster_result(
            snapshot,
            dialects_db=dialects_db,
            query_db=query_db,
            progress_callback=_progress_callback,
        )
        result = annotate_cluster_result_cache(
            result,
            job_hash=job_hash,
            cache_hit=False,
            cache_source="none",
        )
        set_cached_cluster_result(job_hash, result)
        if is_cancel_requested(task_id):
            clear_inflight_task_id(job_hash, task_id=task_id)
            return

        task_manager.update_task(
            task_id,
            progress=98.0,
            message="正在写入聚类结果",
        )
        result_path = write_result(task_id, result)

        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message="聚类任务已完成",
                data={
                    "result_path": str(result_path),
                    "summary": build_task_summary(snapshot, result=result),
                    "job_hash": job_hash,
                    "execution_time_ms": (result.get("metadata") or {}).get("execution_time_ms"),
                    "performance": (result.get("metadata") or {}).get("performance"),
                },
        )
        clear_inflight_task_id(job_hash, task_id=task_id)
    except Exception as exc:
        logger.exception("cluster job failed: %s", exc)
        if is_cancel_requested(task_id):
            task_manager.update_task(
                task_id,
                status="canceled",
                message="聚类任务已取消",
            )
            clear_inflight_task_id(job_hash, task_id=task_id)
            return
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(exc),
            message=f"聚类任务失败: {exc}",
        )
        clear_inflight_task_id(job_hash, task_id=task_id)


__all__ = [
    "build_cluster_distance_state",
    "build_cluster_final_result",
    "build_cluster_prepare_state",
    "build_cluster_result",
    "build_task_summary",
    "get_cluster_result",
    "get_task_status_payload",
    "resolve_cluster_groups",
    "resolve_cluster_job_snapshot",
    "run_cluster_job",
]
