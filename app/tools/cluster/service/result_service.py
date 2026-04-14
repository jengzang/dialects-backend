"""
cluster 结果整形层。

前面的 service 主要产出的是内部中间态，这一层负责把它们拼成前端直接可用的结果 JSON。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.tools.cluster.config import DEFAULT_PHONEME_MODE
from app.tools.cluster.utils import dedupe, public_location_detail


def build_task_summary(snapshot: Dict[str, Any], result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """构建任务摘要，用于创建任务后的回执和任务轮询。"""
    location_resolution = snapshot.get("location_resolution") or {}
    groups = snapshot.get("groups") or []
    clustering = snapshot.get("clustering") or {}
    summary = {
        "algorithm": clustering.get("algorithm"),
        "phoneme_mode": clustering.get("phoneme_mode", DEFAULT_PHONEME_MODE),
        "legacy_metric_mode": clustering.get("metric_mode"),
        "group_count": len(groups),
        "group_char_counts": {group["label"]: group["char_count"] for group in groups},
        "requested_location_count": location_resolution.get("requested_location_count", 0),
        "requested_region_count": location_resolution.get("requested_region_count", 0),
        "matched_location_count": location_resolution.get("matched_location_count", 0),
        "matched_location_count_before_filter": location_resolution.get(
            "matched_location_count_before_filter", 0
        ),
        "filtered_special_location_count": location_resolution.get(
            "filtered_special_location_count", 0
        ),
        "include_special_locations": location_resolution.get("include_special_locations", False),
    }
    if result:
        result_summary = result.get("summary") or {}
        summary.update(
            {
                "effective_location_count": result_summary.get("effective_location_count", 0),
                "cluster_count": result_summary.get("cluster_count", 0),
                "execution_space": (result.get("metadata") or {}).get("execution_space"),
            }
        )
    return summary


def build_group_diagnostics(
    group_models: Sequence[Dict[str, Any]],
    matched_locations: Sequence[str],
    effective_locations: Sequence[str],
) -> List[Dict[str, Any]]:
    """为每个 group 输出覆盖率、缺失地点、权重和告警等诊断信息。"""
    diagnostics: List[Dict[str, Any]] = []
    for group in group_models:
        missing_locations = [
            location
            for location in effective_locations
            if group["locations"][location]["present_char_count"] == 0
        ]
        diagnostics.append(
            {
                "label": group["label"],
                "source_mode": group["source_mode"],
                "compare_dimension": group["compare_dimension"],
                "char_count": group["char_count"],
                "sample_chars": group["sample_chars"],
                "group_weight": group["group_weight"],
                "use_phonetic_values": group["use_phonetic_values"],
                "phonetic_value_weight": group["phonetic_value_weight"],
                "matched_location_count": len(matched_locations),
                "effective_location_count": len(group["effective_locations"]),
                "coverage_ratio": group["coverage_ratio"],
                "missing_locations": missing_locations,
                "resolver": group["resolver"],
                "cache_hit": group["cache_hit"],
                "warnings": group["warnings"],
            }
        )
    return diagnostics


def build_assignments(
    locations: Sequence[str],
    labels: np.ndarray,
    location_details: Dict[str, Dict[str, Any]],
    extra_values: Optional[np.ndarray] = None,
    extra_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """把每个地点映射到聚类标签，并附带展示字段与附加指标。"""
    assignments: List[Dict[str, Any]] = []
    for index, location in enumerate(locations):
        location_detail = public_location_detail(location_details.get(location, {"location": location}))
        item = {
            "location": location,
            "cluster_id": int(labels[index]),
            "province": location_detail.get("province"),
            "city": location_detail.get("city"),
            "county": location_detail.get("county"),
            "town": location_detail.get("town"),
            "coordinates": location_detail.get("coordinates"),
            "yindian_region": location_detail.get("yindian_region"),
            "map_region": location_detail.get("map_region"),
        }
        if extra_values is not None and extra_key:
            item[extra_key] = float(extra_values[index])
        assignments.append(item)
    return assignments


def collect_cluster_warnings(
    *,
    legacy_metric_mode: Optional[str],
    phoneme_mode: str,
    filtered_special_locations: Sequence[str],
    dropped_locations: Sequence[str],
    group_diagnostics: Sequence[Dict[str, Any]],
) -> List[str]:
    """汇总并去重所有全局与分组级别的告警。"""
    warnings: List[str] = []
    if legacy_metric_mode:
        warnings.append(
            f"legacy metric_mode={legacy_metric_mode} 已忽略，当前按 phoneme_mode={phoneme_mode} 执行"
        )
    if filtered_special_locations:
        warnings.append(
            f"已按默认规则过滤特殊点 {len(filtered_special_locations)} 个: "
            f"{', '.join(filtered_special_locations[:20])}"
        )
    if dropped_locations:
        warnings.append(f"以下地点无有效聚类数据，已跳过: {', '.join(dropped_locations[:20])}")
    for group in group_diagnostics:
        warnings.extend(group["warnings"])
    return dedupe(warnings)


def build_result_payload(
    *,
    snapshot: Dict[str, Any],
    algorithm: str,
    phoneme_mode: str,
    legacy_metric_mode: Optional[str],
    matched_locations: Sequence[str],
    effective_locations: Sequence[str],
    dropped_locations: Sequence[str],
    labels: np.ndarray,
    assignments: List[Dict[str, Any]],
    group_diagnostics: List[Dict[str, Any]],
    metrics: Dict[str, float],
    execution_space: str,
    execution_time_ms: int,
    performance: Dict[str, float],
    phoneme_mode_params: Dict[str, float],
    warnings: List[str],
    location_details: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """生成最终结果 JSON，作为 `/result` 接口直接返回的数据结构。"""
    cluster_count = len({label for label in labels.tolist() if label != -1})
    public_location_details = {
        location: public_location_detail(detail)
        for location, detail in location_details.items()
    }
    return {
        "summary": {
            "algorithm": algorithm,
            "phoneme_mode": phoneme_mode,
            "legacy_metric_mode": legacy_metric_mode,
            "group_count": len(snapshot["groups"]),
            "requested_location_count": snapshot["location_resolution"]["requested_location_count"],
            "requested_region_count": snapshot["location_resolution"]["requested_region_count"],
            "matched_location_count": len(matched_locations),
            "matched_location_count_before_filter": snapshot["location_resolution"].get(
                "matched_location_count_before_filter", len(matched_locations)
            ),
            "filtered_special_location_count": snapshot["location_resolution"].get(
                "filtered_special_location_count", 0
            ),
            "effective_location_count": len(effective_locations),
            "cluster_count": cluster_count,
            "noise_count": int(np.sum(labels == -1)) if algorithm == "dbscan" else 0,
        },
        "location_resolution": {
            **snapshot["location_resolution"],
            "location_details": public_location_details,
            "effective_locations": list(effective_locations),
            "effective_location_count": len(effective_locations),
            "dropped_locations": list(dropped_locations),
        },
        "groups": group_diagnostics,
        "assignments": assignments,
        "metrics": metrics,
        "metadata": {
            "execution_space": execution_space,
            "phoneme_mode": phoneme_mode,
            "distance_mode": "phoneme_correspondence",
            "legacy_metric_mode_ignored": bool(legacy_metric_mode),
            "phoneme_mode_params": phoneme_mode_params,
            "execution_time_ms": execution_time_ms,
            "performance": performance,
            "warnings": warnings,
        },
    }
