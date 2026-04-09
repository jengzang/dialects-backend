"""
Cluster request resolution services.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Sequence

from app.common.path import QUERY_DB_USER
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations
from app.service.geo.match_input_tip import match_locations_batch_exact
from app.tools.cluster.config import DEFAULT_FILTERED_YINDIAN_REGIONS, FEATURE_COLUMN_MAP
from app.tools.cluster.service.loader_service import (
    load_location_details,
    resolve_preset_filter_chars,
    resolve_preset_path_chars,
)
from app.tools.cluster.utils import dedupe, now_ms


def normalize_char_input(raw_value: Any) -> List[str]:
    if raw_value is None:
        return []

    if isinstance(raw_value, str):
        items = [raw_value]
    elif isinstance(raw_value, (list, tuple, set)):
        items = list(raw_value)
    else:
        items = [str(raw_value)]

    chars: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        parts = [part for part in re.split(r"[\s,，、;；|/]+", text) if part]
        if not parts:
            continue
        for part in parts:
            chars.extend(ch for ch in part if not ch.isspace())
    return dedupe(chars)


def build_group_label(group: Dict[str, Any], index: int) -> str:
    label = str(group.get("label") or "").strip()
    return label or f"group_{index + 1}"


def resolve_group_sync(group: Dict[str, Any], index: int) -> Dict[str, Any]:
    label = build_group_label(group, index)

    if group.get("resolved_chars") is not None:
        chars = normalize_char_input(group.get("resolved_chars"))
        resolved = {
            "chars": chars,
            "query_labels": [],
            "cache_hit": False,
            "cache_key": None,
            "resolver": "resolved_chars",
        }
    elif group.get("source_mode") == "custom":
        chars = normalize_char_input(group.get("custom_chars"))
        resolved = {
            "chars": chars,
            "query_labels": [],
            "cache_hit": False,
            "cache_key": None,
            "resolver": "custom_chars",
        }
    elif group.get("path_strings"):
        resolved = resolve_preset_path_chars(group, normalize_char_input)
    else:
        resolved = resolve_preset_filter_chars(group, normalize_char_input)

    chars = dedupe(resolved["chars"])
    return {
        "label": label,
        "source_mode": group.get("source_mode"),
        "table_name": group.get("table_name", "characters"),
        "path_strings": group.get("path_strings"),
        "column": group.get("column"),
        "combine_query": bool(group.get("combine_query")),
        "filters": group.get("filters"),
        "exclude_columns": group.get("exclude_columns"),
        "compare_dimension": group.get("compare_dimension"),
        "feature_column": FEATURE_COLUMN_MAP[group.get("compare_dimension")],
        "group_weight": float(group.get("group_weight", 1.0)),
        "use_phonetic_values": bool(group.get("use_phonetic_values", False)),
        "phonetic_value_weight": float(group.get("phonetic_value_weight", 0.2)),
        "resolved_chars": chars,
        "char_count": len(chars),
        "sample_chars": chars[:12],
        "cache_hit": resolved["cache_hit"],
        "cache_key": resolved["cache_key"],
        "resolver": resolved["resolver"],
        "query_labels": resolved["query_labels"],
    }


async def resolve_cluster_groups(groups: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [resolve_group_sync(group, index) for index, group in enumerate(groups)]


def is_default_filtered_location(location_detail: Optional[Dict[str, Any]]) -> bool:
    if not location_detail:
        return False
    return (location_detail.get("yindian_region") or "") in DEFAULT_FILTERED_YINDIAN_REGIONS


def resolve_locations(
    locations: Sequence[str],
    regions: Sequence[str],
    region_mode: str,
    query_db: str,
    include_special_locations: bool = False,
    requested_locations_raw: Optional[Sequence[str]] = None,
    requested_regions_raw: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    expanded_inputs = query_dialect_abbreviations(
        region_input=list(regions or []),
        location_sequence=list(locations or []),
        db_path=query_db,
        region_mode=region_mode,
    )

    matched_results = match_locations_batch_exact(
        " ".join(expanded_inputs),
        query_db=query_db,
    )
    matched_locations = dedupe(
        abbr
        for abbrs, success_flag, *_ in matched_results
        if success_flag == 1
        for abbr in abbrs
    )
    location_details_all = load_location_details(matched_locations, query_db)
    filtered_special_locations: List[str] = []
    if not include_special_locations:
        filtered_special_locations = [
            location
            for location in matched_locations
            if is_default_filtered_location(location_details_all.get(location))
        ]
        blocked = set(filtered_special_locations)
        matched_locations = [
            location for location in matched_locations if location not in blocked
        ]
    location_details = {
        location: location_details_all[location]
        for location in matched_locations
        if location in location_details_all
    }

    return {
        "requested_locations": list(requested_locations_raw or locations or []),
        "requested_regions": list(requested_regions_raw or regions or []),
        "region_mode": region_mode,
        "include_special_locations": bool(include_special_locations),
        "expanded_inputs": dedupe(expanded_inputs),
        "matched_locations": matched_locations,
        "location_details": location_details,
        "matched_location_count_before_filter": len(location_details_all),
        "filtered_special_locations": filtered_special_locations,
        "filtered_special_location_count": len(filtered_special_locations),
        "requested_location_count": len(list(requested_locations_raw or locations or [])),
        "requested_region_count": len(list(requested_regions_raw or regions or [])),
        "expanded_input_count": len(dedupe(expanded_inputs)),
        "matched_location_count": len(matched_locations),
    }


async def resolve_cluster_job_snapshot(
    payload: Dict[str, Any],
    query_db: str = QUERY_DB_USER,
) -> Dict[str, Any]:
    start_time = time.perf_counter()
    groups = await resolve_cluster_groups(payload.get("groups") or [])
    empty_groups = [group["label"] for group in groups if not group["resolved_chars"]]
    if empty_groups:
        raise ValueError(f"以下组未命中任何汉字: {', '.join(empty_groups)}")

    location_resolution = resolve_locations(
        locations=payload.get("locations") or [],
        regions=payload.get("regions") or [],
        region_mode=payload.get("region_mode", "yindian"),
        query_db=query_db,
        include_special_locations=bool(payload.get("include_special_locations", False)),
        requested_locations_raw=payload.get("requested_locations_raw") or [],
        requested_regions_raw=payload.get("requested_regions_raw") or [],
    )
    if len(location_resolution["matched_locations"]) < 2:
        if (
            not location_resolution.get("include_special_locations")
            and location_resolution.get("filtered_special_location_count", 0) > 0
        ):
            raise ValueError(
                "默认过滤特殊点后，可参与聚类的地点不足 2 个；如需保留这些点，请传 include_special_locations=true"
            )
        raise ValueError("可参与聚类的地点不足 2 个")

    return {
        "groups": groups,
        "location_resolution": location_resolution,
        "clustering": payload.get("clustering") or {},
        "requested_inputs": {
            "locations": payload.get("requested_locations_raw") or payload.get("locations") or [],
            "regions": payload.get("requested_regions_raw") or payload.get("regions") or [],
            "region_mode": payload.get("region_mode", "yindian"),
            "include_special_locations": bool(payload.get("include_special_locations", False)),
        },
        "created_at_ms": now_ms(),
        "performance": {
            "snapshot_ms": round((time.perf_counter() - start_time) * 1000.0, 3),
        },
    }
