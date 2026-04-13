"""
Cluster service facade.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

from app.common.path import DIALECTS_DB_USER
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


def build_cluster_result(
    snapshot: Dict[str, Any],
    dialects_db: str = DIALECTS_DB_USER,
) -> Dict[str, Any]:
    start_time = time.perf_counter()
    performance = dict(snapshot.get("performance") or {})

    groups = snapshot["groups"]
    clustering = snapshot["clustering"]
    phoneme_mode = clustering.get("phoneme_mode", DEFAULT_PHONEME_MODE)
    legacy_metric_mode = clustering.get("metric_mode")
    matched_locations = snapshot["location_resolution"]["matched_locations"]
    all_chars = dedupe(char for group in groups for char in group["resolved_chars"])
    requested_dimensions = sorted(
        {group["compare_dimension"] for group in groups if group.get("compare_dimension")}
    )

    load_start = time.perf_counter()
    dialect_data = load_dialect_rows(
        matched_locations,
        all_chars,
        dialects_db,
        requested_dimensions=requested_dimensions,
    )
    performance["load_rows_ms"] = round((time.perf_counter() - load_start) * 1000.0, 3)

    encode_start = time.perf_counter()
    dimension_token_catalogs = build_dimension_token_catalogs(groups, dialect_data)
    group_models = [
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
            group["locations"][location]["present_char_count"] > 0 for group in group_models
        )
    ]
    if len(effective_locations) < 2:
        raise ValueError("有效地点不足 2 个，无法执行聚类")

    group_diagnostics = build_group_diagnostics(
        group_models,
        matched_locations,
        effective_locations,
    )
    performance["encode_ms"] = round((time.perf_counter() - encode_start) * 1000.0, 3)
    dropped_locations = [
        location for location in matched_locations if location not in effective_locations
    ]

    inventory_profiles = {}
    inventory_profiles_start = time.perf_counter()
    if phoneme_mode == "anchored_inventory":
        inventory_profiles = load_dimension_inventory_profiles(
            effective_locations,
            [group["compare_dimension"] for group in groups],
            dialects_db,
        )
    performance["inventory_profiles_ms"] = round(
        (time.perf_counter() - inventory_profiles_start) * 1000.0,
        3,
    )

    bucket_models = {}
    bucket_models_start = time.perf_counter()
    if phoneme_mode == "shared_request_identity":
        bucket_models = build_dimension_bucket_models(
            groups,
            effective_locations,
            dialect_data,
            dimension_token_catalogs,
        )
    performance["bucket_models_ms"] = round(
        (time.perf_counter() - bucket_models_start) * 1000.0,
        3,
    )

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
    algorithm = clustering["algorithm"]
    execution_space = choose_execution_space(algorithm=algorithm)
    location_detail_start = time.perf_counter()
    location_details = load_location_details(matched_locations, dialects_db)
    performance["location_details_ms"] = round(
        (time.perf_counter() - location_detail_start) * 1000.0,
        3,
    )

    labels: np.ndarray
    assignments: List[Dict[str, Any]]
    metrics_matrix: Optional[np.ndarray] = None

    cluster_start = time.perf_counter()
    if algorithm == "agglomerative":
        n_clusters = int(clustering["n_clusters"])
        if n_clusters > len(effective_locations):
            raise ValueError("n_clusters 不能大于有效地点数")
        labels = run_agglomerative(distance_matrix, n_clusters, clustering.get("linkage", "average"))
        assignments = build_assignments(effective_locations, labels, location_details)
    elif algorithm == "dbscan":
        labels = run_dbscan(
            distance_matrix,
            eps=float(clustering.get("eps", 0.5)),
            min_samples=int(clustering.get("min_samples", 5)),
        )
        assignments = build_assignments(effective_locations, labels, location_details)
    elif algorithm == "kmeans":
        n_clusters = int(clustering["n_clusters"])
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
            random_state=int(clustering.get("random_state", 42)),
        )
        assignments = build_assignments(
            effective_locations,
            labels,
            location_details,
            extra_values=centroid_distance,
            extra_key="distance_to_centroid",
        )
    elif algorithm == "gmm":
        n_clusters = int(clustering["n_clusters"])
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
            random_state=int(clustering.get("random_state", 42)),
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
    execution_time_ms = int((time.perf_counter() - start_time) * 1000)

    return build_result_payload(
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
        phoneme_mode_params=phoneme_mode_params,
        warnings=warnings,
        location_details=location_details,
    )


def run_cluster_job(
    task_id: str,
    dialects_db: str = DIALECTS_DB_USER,
):
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
    job_hash = (task.get("data") or {}).get("job_hash") or build_cluster_job_hash(
        snapshot,
        dialects_db,
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
                },
            )
            clear_inflight_task_id(job_hash, task_id=task_id)
            return

        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=15.0,
            message="正在读取方言数据并构建聚类输入",
        )

        result = build_cluster_result(snapshot, dialects_db=dialects_db)
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
            progress=90.0,
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
    "build_cluster_result",
    "build_task_summary",
    "get_cluster_result",
    "get_task_status_payload",
    "resolve_cluster_groups",
    "resolve_cluster_job_snapshot",
    "run_cluster_job",
]
