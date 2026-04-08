"""
Dialect clustering service.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from app.common.constants import get_table_schema, validate_table_name
from app.common.path import CHARACTERS_DB_PATH, DIALECTS_DB_USER, QUERY_DB_USER
from app.redis_client import sync_redis_client
from app.service.core.new_pho import generate_cache_key, process_chars_status
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations
from app.service.geo.match_input_tip import match_locations_batch_exact
from app.sql.db_pool import get_db_pool
from app.tools.file_manager import file_manager
from app.tools.task_manager import TaskStatus, task_manager

logger = logging.getLogger(__name__)

FEATURE_COLUMN_MAP = {
    "initial": "聲母",
    "final": "韻母",
    "tone": "聲調",
}
TASK_TOOL_NAME = "cluster"
CACHE_TTL_SECONDS = 600
DIST_EPSILON = 1e-12


def _quote_identifier(name: str) -> str:
    safe_name = name.replace('"', '""')
    return f'"{safe_name}"'


def _now_ms() -> int:
    return int(time.time() * 1000)


def _dedupe(items: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


def _normalize_char_input(raw_value: Any) -> List[str]:
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
    return _dedupe(chars)


def _cache_get_json(key: str) -> Optional[Any]:
    try:
        cached = sync_redis_client.get(key)
        if cached:
            return json.loads(cached)
    except Exception as exc:
        logger.warning("cluster cache read failed: %s", exc)
    return None


def _cache_set_json(key: str, value: Any, ttl: int = CACHE_TTL_SECONDS):
    try:
        sync_redis_client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
    except Exception as exc:
        logger.warning("cluster cache write failed: %s", exc)


def _build_filters_cache_key(group: Dict[str, Any]) -> str:
    key_payload = {
        "table_name": group.get("table_name", "characters"),
        "filters": group.get("filters") or {},
        "exclude_columns": sorted(group.get("exclude_columns") or []),
    }
    encoded = json.dumps(
        key_payload, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    import hashlib

    return "cluster:filters:" + hashlib.md5(encoded).hexdigest()


def _build_group_label(group: Dict[str, Any], index: int) -> str:
    label = str(group.get("label") or "").strip()
    return label or f"group_{index + 1}"


def _resolve_preset_path_chars(group: Dict[str, Any]) -> Dict[str, Any]:
    path_strings = group.get("path_strings") or []
    cache_key = generate_cache_key(
        path_strings=path_strings,
        column=group.get("column"),
        combine_query=bool(group.get("combine_query")),
        exclude_columns=group.get("exclude_columns"),
        table=group.get("table_name", "characters"),
    )

    cached_items = _cache_get_json(cache_key)
    cache_hit = cached_items is not None
    if cached_items is None:
        cached_items = process_chars_status(
            path_strings=path_strings,
            column=group.get("column"),
            combine_query=bool(group.get("combine_query")),
            exclude_columns=group.get("exclude_columns"),
            table=group.get("table_name", "characters"),
        )
        _cache_set_json(cache_key, cached_items)

    chars: List[str] = []
    queries: List[str] = []
    for item in cached_items or []:
        chars.extend(_normalize_char_input(item.get("chars") or item.get("漢字") or item.get("汉字")))
        query_name = str(item.get("query") or "").strip()
        if query_name:
            queries.append(query_name)

    return {
        "chars": _dedupe(chars),
        "query_labels": _dedupe(queries),
        "cache_hit": cache_hit,
        "cache_key": cache_key,
        "resolver": "charlist_payload",
    }


def _resolve_preset_filter_chars(group: Dict[str, Any]) -> Dict[str, Any]:
    table_name = group.get("table_name", "characters")
    filters = group.get("filters") or {}

    if not validate_table_name(table_name):
        raise ValueError(f"Invalid table_name: {table_name}")

    schema = get_table_schema(table_name)
    valid_columns = set(schema["hierarchy"])
    invalid_columns = sorted(set(filters) - valid_columns)
    if invalid_columns:
        raise ValueError(
            f"Invalid filter columns for table '{table_name}': {', '.join(invalid_columns)}"
        )

    cache_key = _build_filters_cache_key(group)
    cached = _cache_get_json(cache_key)
    cache_hit = cached is not None
    if cached is not None:
        return {
            "chars": _normalize_char_input(cached.get("chars")),
            "query_labels": [f"{table_name}:filters"],
            "cache_hit": cache_hit,
            "cache_key": cache_key,
            "resolver": "structured_filters",
        }

    conditions: List[str] = []
    params: List[str] = []
    for column, values in filters.items():
        uniq_values = _dedupe(values)
        if not uniq_values:
            continue

        sub_conditions: List[str] = []
        for value in uniq_values:
            if column == "等" and value == "三":
                sub_conditions.append(f"{_quote_identifier(column)} IN (?, ?, ?, ?)")
                params.extend(["三A", "三B", "三C", "三銳"])
            else:
                sub_conditions.append(f"{_quote_identifier(column)} = ?")
                params.append(value)
        conditions.append(f"({' OR '.join(sub_conditions)})")

    if not conditions:
        return {
            "chars": [],
            "query_labels": [f"{table_name}:filters"],
            "cache_hit": False,
            "cache_key": cache_key,
            "resolver": "structured_filters",
        }

    char_column = schema["char_column"]
    query = (
        f"SELECT DISTINCT {_quote_identifier(char_column)} "
        f"FROM {_quote_identifier(table_name)} "
        f"WHERE {' AND '.join(conditions)}"
    )

    for exclude_column in group.get("exclude_columns") or []:
        query += (
            f" AND ({_quote_identifier(exclude_column)} != 1 "
            f"AND {_quote_identifier(exclude_column)} != '1')"
        )

    pool = get_db_pool(CHARACTERS_DB_PATH)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        chars = [row[0] for row in cursor.fetchall() if row[0]]

    payload = {"chars": _dedupe(chars)}
    _cache_set_json(cache_key, payload)

    return {
        "chars": payload["chars"],
        "query_labels": [f"{table_name}:filters"],
        "cache_hit": cache_hit,
        "cache_key": cache_key,
        "resolver": "structured_filters",
    }


def _resolve_group_sync(group: Dict[str, Any], index: int) -> Dict[str, Any]:
    label = _build_group_label(group, index)

    if group.get("resolved_chars") is not None:
        chars = _normalize_char_input(group.get("resolved_chars"))
        resolved = {
            "chars": chars,
            "query_labels": [],
            "cache_hit": False,
            "cache_key": None,
            "resolver": "resolved_chars",
        }
    elif group.get("source_mode") == "custom":
        chars = _normalize_char_input(group.get("custom_chars"))
        resolved = {
            "chars": chars,
            "query_labels": [],
            "cache_hit": False,
            "cache_key": None,
            "resolver": "custom_chars",
        }
    elif group.get("path_strings"):
        resolved = _resolve_preset_path_chars(group)
    else:
        resolved = _resolve_preset_filter_chars(group)

    chars = _dedupe(resolved["chars"])
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
        "phonetic_value_weight": float(group.get("phonetic_value_weight", 1.0)),
        "phonetic_mix": (
            float(group.get("phonetic_value_weight", 1.0))
            / (1.0 + float(group.get("phonetic_value_weight", 1.0)))
            if bool(group.get("use_phonetic_values", False))
            else 0.0
        ),
        "resolved_chars": chars,
        "char_count": len(chars),
        "sample_chars": chars[:12],
        "cache_hit": resolved["cache_hit"],
        "cache_key": resolved["cache_key"],
        "resolver": resolved["resolver"],
        "query_labels": resolved["query_labels"],
    }


async def resolve_cluster_groups(groups: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_resolve_group_sync(group, index) for index, group in enumerate(groups)]


def _resolve_locations(
    locations: Sequence[str],
    regions: Sequence[str],
    region_mode: str,
    query_db: str,
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
    matched_locations = _dedupe(
        abbr
        for abbrs, success_flag, *_ in matched_results
        if success_flag == 1
        for abbr in abbrs
    )

    return {
        "requested_locations": list(requested_locations_raw or locations or []),
        "requested_regions": list(requested_regions_raw or regions or []),
        "region_mode": region_mode,
        "expanded_inputs": _dedupe(expanded_inputs),
        "matched_locations": matched_locations,
        "requested_location_count": len(list(requested_locations_raw or locations or [])),
        "requested_region_count": len(list(requested_regions_raw or regions or [])),
        "expanded_input_count": len(_dedupe(expanded_inputs)),
        "matched_location_count": len(matched_locations),
    }


async def resolve_cluster_job_snapshot(
    payload: Dict[str, Any],
    query_db: str = QUERY_DB_USER,
) -> Dict[str, Any]:
    groups = await resolve_cluster_groups(payload.get("groups") or [])
    empty_groups = [group["label"] for group in groups if not group["resolved_chars"]]
    if empty_groups:
        raise ValueError(f"以下组未命中任何汉字: {', '.join(empty_groups)}")

    location_resolution = _resolve_locations(
        locations=payload.get("locations") or [],
        regions=payload.get("regions") or [],
        region_mode=payload.get("region_mode", "yindian"),
        query_db=query_db,
        requested_locations_raw=payload.get("requested_locations_raw") or [],
        requested_regions_raw=payload.get("requested_regions_raw") or [],
    )
    if len(location_resolution["matched_locations"]) < 2:
        raise ValueError("可参与聚类的地点不足 2 个")

    return {
        "groups": groups,
        "location_resolution": location_resolution,
        "clustering": payload.get("clustering") or {},
        "requested_inputs": {
            "locations": payload.get("requested_locations_raw") or payload.get("locations") or [],
            "regions": payload.get("requested_regions_raw") or payload.get("regions") or [],
            "region_mode": payload.get("region_mode", "yindian"),
        },
        "created_at_ms": _now_ms(),
    }


def build_task_summary(snapshot: Dict[str, Any], result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    location_resolution = snapshot.get("location_resolution") or {}
    groups = snapshot.get("groups") or []
    summary = {
        "algorithm": (snapshot.get("clustering") or {}).get("algorithm"),
        "group_count": len(groups),
        "group_char_counts": {group["label"]: group["char_count"] for group in groups},
        "requested_location_count": location_resolution.get("requested_location_count", 0),
        "requested_region_count": location_resolution.get("requested_region_count", 0),
        "matched_location_count": location_resolution.get("matched_location_count", 0),
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


def get_task_status_payload(task_id: str) -> Optional[Dict[str, Any]]:
    task = task_manager.get_task(task_id)
    if not task:
        return None

    return {
        "task_id": task_id,
        "status": str(task.get("status")),
        "progress": float(task.get("progress", 0.0)),
        "message": str(task.get("message") or ""),
        "created_at": float(task.get("created_at", 0.0)),
        "updated_at": float(task.get("updated_at", 0.0)),
        "summary": (task.get("data") or {}).get("summary"),
    }


def _task_result_path(task_id: str) -> Path:
    return file_manager.get_task_dir(task_id, TASK_TOOL_NAME) / "result.json"


def _write_result(task_id: str, result: Dict[str, Any]) -> Path:
    result_path = _task_result_path(task_id)
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    return result_path


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


def _chunked(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _load_dialect_rows(
    locations: Sequence[str],
    chars: Sequence[str],
    db_path: str,
) -> Dict[str, Dict[str, Dict[str, set[str]]]]:
    data: Dict[str, Dict[str, Dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: {"initial": set(), "final": set(), "tone": set()})
    )
    if not locations or not chars:
        return data

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        for loc_batch in _chunked(list(locations), 80):
            for char_batch in _chunked(list(chars), 240):
                loc_placeholders = ",".join("?" * len(loc_batch))
                char_placeholders = ",".join("?" * len(char_batch))
                query = f"""
                    SELECT 簡稱, 漢字, 聲母, 韻母, 聲調
                    FROM dialects
                    WHERE 簡稱 IN ({loc_placeholders})
                      AND 漢字 IN ({char_placeholders})
                """
                cursor.execute(query, list(loc_batch) + list(char_batch))
                for row in cursor.fetchall():
                    location = row[0]
                    char = row[1]
                    if row[2]:
                        data[location][char]["initial"].add(str(row[2]).strip())
                    if row[3]:
                        data[location][char]["final"].add(str(row[3]).strip())
                    if row[4]:
                        data[location][char]["tone"].add(str(row[4]).strip())
    return data


def _normalize_distribution(counter: Counter[str]) -> Dict[str, float]:
    total = float(sum(counter.values()))
    if total <= 0:
        return {}
    return {key: float(value / total) for key, value in counter.items() if value > 0}


def _build_group_model(
    group: Dict[str, Any],
    locations: Sequence[str],
    dialect_data: Dict[str, Dict[str, Dict[str, set[str]]]],
) -> Dict[str, Any]:
    dimension = group["compare_dimension"]
    vocab: set[str] = set()
    location_models: Dict[str, Dict[str, Any]] = {}

    for location in locations:
        location_char_data = dialect_data.get(location, {})
        distribution_counter: Counter[str] = Counter()
        token_map: Dict[str, str] = {}
        raw_values: Dict[str, set[str]] = {}
        present_char_count = 0

        for char in group["resolved_chars"]:
            values = set(location_char_data.get(char, {}).get(dimension, set()))
            if not values:
                continue

            normalized_values = sorted(value for value in values if value)
            if not normalized_values:
                continue

            present_char_count += 1
            raw_values[char] = set(normalized_values)
            token_map[char] = "|".join(normalized_values)
            share = 1.0 / len(normalized_values)
            for value in normalized_values:
                distribution_counter[value] += share
                vocab.add(value)

        distribution = _normalize_distribution(distribution_counter)
        location_models[location] = {
            "distribution": distribution,
            "token_map": token_map,
            "raw_values": raw_values,
            "present_char_count": present_char_count,
            "coverage": (
                float(present_char_count / group["char_count"])
                if group["char_count"]
                else 0.0
            ),
            "unique_value_count": len(distribution),
        }

    effective_locations = [
        location
        for location in locations
        if location_models[location]["present_char_count"] > 0
    ]
    warnings: List[str] = []
    if not effective_locations:
        warnings.append("该组在所有地点上都没有有效读音数据")

    return {
        **group,
        "locations": location_models,
        "vocabulary": sorted(vocab),
        "effective_locations": effective_locations,
        "coverage_ratio": (
            float(len(effective_locations) / len(locations)) if locations else 0.0
        ),
        "warnings": warnings,
    }


def _js_distance(dist_a: Dict[str, float], dist_b: Dict[str, float]) -> float:
    if not dist_a and not dist_b:
        return 0.0
    if not dist_a or not dist_b:
        return 1.0

    vocab = sorted(set(dist_a) | set(dist_b))
    p = np.array([dist_a.get(value, 0.0) for value in vocab], dtype=float)
    q = np.array([dist_b.get(value, 0.0) for value in vocab], dtype=float)
    m = (p + q) / 2.0

    def _kl_div(lhs: np.ndarray, rhs: np.ndarray) -> float:
        mask = lhs > 0
        if not np.any(mask):
            return 0.0
        return float(np.sum(lhs[mask] * np.log((lhs[mask] + DIST_EPSILON) / (rhs[mask] + DIST_EPSILON))))

    js = 0.5 * _kl_div(p, m) + 0.5 * _kl_div(q, m)
    return min(1.0, max(0.0, float(math.sqrt(js))))


def _conditional_entropy_distance(
    token_map_a: Dict[str, str],
    token_map_b: Dict[str, str],
) -> float:
    shared_chars = sorted(set(token_map_a) & set(token_map_b))
    if not shared_chars:
        return 1.0

    pairs = [(token_map_a[char], token_map_b[char]) for char in shared_chars]
    count_xy = Counter(pairs)
    count_x = Counter(x for x, _ in pairs)
    count_y = Counter(y for _, y in pairs)
    total = float(len(pairs))

    h_y_given_x = 0.0
    for (token_x, token_y), freq in count_xy.items():
        prob_xy = freq / total
        prob_y_given_x = freq / count_x[token_x]
        h_y_given_x -= prob_xy * math.log(prob_y_given_x + DIST_EPSILON)

    h_x_given_y = 0.0
    for (token_x, token_y), freq in count_xy.items():
        prob_xy = freq / total
        prob_x_given_y = freq / count_y[token_y]
        h_x_given_y -= prob_xy * math.log(prob_x_given_y + DIST_EPSILON)

    normalizer = math.log(max(len(count_x), len(count_y), 2))
    if normalizer <= 0:
        return 0.0

    return min(1.0, max(0.0, 0.5 * (h_y_given_x + h_x_given_y) / normalizer))


def _phonetic_value_distance(
    values_a: Dict[str, set[str]],
    values_b: Dict[str, set[str]],
) -> float:
    shared_chars = sorted(set(values_a) & set(values_b))
    if not shared_chars:
        return 1.0

    distances: List[float] = []
    for char in shared_chars:
        union = values_a[char] | values_b[char]
        if not union:
            continue
        intersection = values_a[char] & values_b[char]
        distances.append(1.0 - (len(intersection) / len(union)))

    if not distances:
        return 1.0
    return float(sum(distances) / len(distances))


def _build_distance_matrix(
    group_models: Sequence[Dict[str, Any]],
    locations: Sequence[str],
) -> np.ndarray:
    size = len(locations)
    matrix = np.zeros((size, size), dtype=float)

    for i in range(size):
        for j in range(i + 1, size):
            total = 0.0
            weight_sum = 0.0
            for group in group_models:
                state_a = group["locations"][locations[i]]
                state_b = group["locations"][locations[j]]
                both_zero = (
                    state_a["present_char_count"] == 0 and state_b["present_char_count"] == 0
                )
                if both_zero:
                    continue

                weight = float(group["group_weight"])
                weight_sum += weight

                if (
                    state_a["present_char_count"] == 0
                    or state_b["present_char_count"] == 0
                ):
                    group_distance = 1.0
                else:
                    corr_distance = _conditional_entropy_distance(
                        state_a["token_map"],
                        state_b["token_map"],
                    )
                    distribution_distance = _js_distance(
                        state_a["distribution"],
                        state_b["distribution"],
                    )
                    phonetic_distance = (
                        _phonetic_value_distance(
                            state_a["raw_values"],
                            state_b["raw_values"],
                        )
                        if group["use_phonetic_values"]
                        else 0.0
                    )
                    mix = float(group["phonetic_mix"])
                    group_distance = (1.0 - mix) * (
                        0.5 * corr_distance + 0.5 * distribution_distance
                    ) + mix * phonetic_distance

                total += weight * group_distance

            distance = (total / weight_sum) if weight_sum > 0 else 1.0
            matrix[i, j] = distance
            matrix[j, i] = distance

    return matrix


def _build_feature_matrix(
    group_models: Sequence[Dict[str, Any]],
    locations: Sequence[str],
) -> np.ndarray:
    blocks: List[np.ndarray] = []
    for group in group_models:
        vocabulary = group["vocabulary"]
        width = len(vocabulary) + 2
        if width <= 0:
            continue

        block = np.zeros((len(locations), width), dtype=float)
        vocab_index = {value: idx for idx, value in enumerate(vocabulary)}
        for row_index, location in enumerate(locations):
            state = group["locations"][location]
            for value, probability in state["distribution"].items():
                if value in vocab_index:
                    block[row_index, vocab_index[value]] = probability
            block[row_index, len(vocabulary)] = state["coverage"]
            block[row_index, len(vocabulary) + 1] = (
                state["unique_value_count"] / max(len(vocabulary), 1)
            )
        blocks.append(block * float(group["group_weight"]))

    if not blocks:
        return np.zeros((len(locations), 1), dtype=float)
    return np.concatenate(blocks, axis=1)


def _classical_mds(distance_matrix: np.ndarray, n_components: int) -> np.ndarray:
    size = distance_matrix.shape[0]
    if size <= 1:
        return np.zeros((size, 1), dtype=float)

    squared = distance_matrix ** 2
    centering = np.eye(size) - np.ones((size, size)) / size
    gram = -0.5 * centering @ squared @ centering
    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    positive = eigenvalues > DIST_EPSILON
    eigenvalues = eigenvalues[positive][:n_components]
    eigenvectors = eigenvectors[:, positive][:, :n_components]
    if eigenvalues.size == 0:
        return np.zeros((size, n_components), dtype=float)
    return eigenvectors * np.sqrt(eigenvalues)


def _prepare_feature_space(matrix: np.ndarray) -> np.ndarray:
    if matrix.shape[0] <= 1:
        return matrix

    scaler = StandardScaler()
    transformed = scaler.fit_transform(matrix)
    if transformed.shape[1] > 24 and transformed.shape[0] > 3:
        max_components = min(24, transformed.shape[0] - 1, transformed.shape[1])
        if max_components >= 2:
            from sklearn.decomposition import PCA

            transformed = PCA(n_components=max_components, random_state=42).fit_transform(
                transformed
            )
    return transformed


def _choose_execution_space(
    algorithm: str,
    group_models: Sequence[Dict[str, Any]],
    feature_matrix: np.ndarray,
    location_count: int,
) -> str:
    if algorithm not in {"kmeans", "gmm"}:
        return "distance_matrix"
    if any(group["use_phonetic_values"] for group in group_models):
        return "embedded_distance"
    if feature_matrix.shape[1] <= max(400, location_count * 6):
        return "feature_space"
    return "embedded_distance"


def _run_agglomerative(
    distance_matrix: np.ndarray,
    n_clusters: int,
    linkage: str,
) -> np.ndarray:
    if linkage == "ward":
        raise ValueError("agglomerative linkage 'ward' is not supported for distance matrices")
    try:
        model = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric="precomputed",
            linkage=linkage,
        )
    except TypeError:
        model = AgglomerativeClustering(
            n_clusters=n_clusters,
            affinity="precomputed",
            linkage=linkage,
        )
    return model.fit_predict(distance_matrix)


def _run_dbscan(distance_matrix: np.ndarray, eps: float, min_samples: int) -> np.ndarray:
    model = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    return model.fit_predict(distance_matrix)


def _run_kmeans(
    matrix: np.ndarray,
    n_clusters: int,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = model.fit_predict(matrix)
    centroid_distance = np.linalg.norm(matrix - model.cluster_centers_[labels], axis=1)
    return labels, centroid_distance


def _run_gmm(
    matrix: np.ndarray,
    n_clusters: int,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    model = GaussianMixture(n_components=n_clusters, random_state=random_state)
    labels = model.fit_predict(matrix)
    membership = model.predict_proba(matrix).max(axis=1)
    return labels, membership


def _compute_metrics(
    labels: np.ndarray,
    execution_matrix: Optional[np.ndarray] = None,
    distance_matrix: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    unique_labels = sorted(label for label in set(labels.tolist()) if label != -1)
    if len(unique_labels) < 2:
        return metrics

    if distance_matrix is not None:
        try:
            metrics["silhouette_score"] = float(
                silhouette_score(distance_matrix, labels, metric="precomputed")
            )
        except Exception:
            pass

    if execution_matrix is None and distance_matrix is not None:
        execution_matrix = _classical_mds(
            distance_matrix,
            n_components=min(8, max(distance_matrix.shape[0] - 1, 1)),
        )

    if execution_matrix is not None:
        try:
            if "silhouette_score" not in metrics:
                metrics["silhouette_score"] = float(
                    silhouette_score(execution_matrix, labels)
                )
        except Exception:
            pass
        try:
            metrics["davies_bouldin_index"] = float(
                davies_bouldin_score(execution_matrix, labels)
            )
        except Exception:
            pass
        try:
            metrics["calinski_harabasz_score"] = float(
                calinski_harabasz_score(execution_matrix, labels)
            )
        except Exception:
            pass

    return metrics


def _build_assignments(
    locations: Sequence[str],
    labels: np.ndarray,
    extra_values: Optional[np.ndarray] = None,
    extra_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    assignments: List[Dict[str, Any]] = []
    for index, location in enumerate(locations):
        item = {
            "location": location,
            "cluster_id": int(labels[index]),
        }
        if extra_values is not None and extra_key:
            item[extra_key] = float(extra_values[index])
        assignments.append(item)
    return assignments


def build_cluster_result(
    snapshot: Dict[str, Any],
    dialects_db: str = DIALECTS_DB_USER,
) -> Dict[str, Any]:
    start_time = time.time()

    groups = snapshot["groups"]
    matched_locations = snapshot["location_resolution"]["matched_locations"]
    all_chars = _dedupe(char for group in groups for char in group["resolved_chars"])
    dialect_data = _load_dialect_rows(matched_locations, all_chars, dialects_db)

    group_models = [
        _build_group_model(group, matched_locations, dialect_data)
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

    group_diagnostics: List[Dict[str, Any]] = []
    dropped_locations = [location for location in matched_locations if location not in effective_locations]
    for group in group_models:
        missing_locations = [
            location
            for location in effective_locations
            if group["locations"][location]["present_char_count"] == 0
        ]
        group_diagnostics.append(
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

    distance_matrix = _build_distance_matrix(group_models, effective_locations)
    feature_matrix = _build_feature_matrix(group_models, effective_locations)

    clustering = snapshot["clustering"]
    algorithm = clustering["algorithm"]
    execution_space = _choose_execution_space(
        algorithm=algorithm,
        group_models=group_models,
        feature_matrix=feature_matrix,
        location_count=len(effective_locations),
    )

    labels: np.ndarray
    assignments: List[Dict[str, Any]]
    metrics_matrix: Optional[np.ndarray] = None

    if algorithm == "agglomerative":
        n_clusters = int(clustering["n_clusters"])
        if n_clusters > len(effective_locations):
            raise ValueError("n_clusters 不能大于有效地点数")
        labels = _run_agglomerative(distance_matrix, n_clusters, clustering.get("linkage", "average"))
        assignments = _build_assignments(effective_locations, labels)
    elif algorithm == "dbscan":
        labels = _run_dbscan(
            distance_matrix,
            eps=float(clustering.get("eps", 0.5)),
            min_samples=int(clustering.get("min_samples", 5)),
        )
        assignments = _build_assignments(effective_locations, labels)
    elif algorithm == "kmeans":
        n_clusters = int(clustering["n_clusters"])
        if n_clusters > len(effective_locations):
            raise ValueError("n_clusters 不能大于有效地点数")
        if execution_space == "feature_space":
            metrics_matrix = _prepare_feature_space(feature_matrix)
        else:
            metrics_matrix = _prepare_feature_space(
                _classical_mds(
                    distance_matrix,
                    n_components=min(8, max(len(effective_locations) - 1, 1)),
                )
            )
        labels, centroid_distance = _run_kmeans(
            metrics_matrix,
            n_clusters=n_clusters,
            random_state=int(clustering.get("random_state", 42)),
        )
        assignments = _build_assignments(
            effective_locations,
            labels,
            extra_values=centroid_distance,
            extra_key="distance_to_centroid",
        )
    elif algorithm == "gmm":
        n_clusters = int(clustering["n_clusters"])
        if n_clusters > len(effective_locations):
            raise ValueError("n_clusters 不能大于有效地点数")
        if execution_space == "feature_space":
            metrics_matrix = _prepare_feature_space(feature_matrix)
        else:
            metrics_matrix = _prepare_feature_space(
                _classical_mds(
                    distance_matrix,
                    n_components=min(8, max(len(effective_locations) - 1, 1)),
                )
            )
        labels, membership = _run_gmm(
            metrics_matrix,
            n_clusters=n_clusters,
            random_state=int(clustering.get("random_state", 42)),
        )
        assignments = _build_assignments(
            effective_locations,
            labels,
            extra_values=membership,
            extra_key="membership_score",
        )
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    metrics = _compute_metrics(
        labels=labels,
        execution_matrix=metrics_matrix,
        distance_matrix=distance_matrix if algorithm in {"agglomerative", "dbscan"} else None,
    )
    cluster_count = len({label for label in labels.tolist() if label != -1})
    execution_time_ms = int((time.time() - start_time) * 1000)

    warnings = []
    if dropped_locations:
        warnings.append(f"以下地点无有效聚类数据，已跳过: {', '.join(dropped_locations[:20])}")

    return {
        "summary": {
            "algorithm": algorithm,
            "group_count": len(groups),
            "requested_location_count": snapshot["location_resolution"]["requested_location_count"],
            "requested_region_count": snapshot["location_resolution"]["requested_region_count"],
            "matched_location_count": len(matched_locations),
            "effective_location_count": len(effective_locations),
            "cluster_count": cluster_count,
            "noise_count": int(np.sum(labels == -1)) if algorithm == "dbscan" else 0,
        },
        "location_resolution": {
            **snapshot["location_resolution"],
            "effective_locations": effective_locations,
            "effective_location_count": len(effective_locations),
            "dropped_locations": dropped_locations,
        },
        "groups": group_diagnostics,
        "assignments": assignments,
        "metrics": metrics,
        "metadata": {
            "execution_space": execution_space,
            "distance_mode": "mixed",
            "execution_time_ms": execution_time_ms,
            "warnings": warnings,
        },
    }


def _is_cancel_requested(task_id: str) -> bool:
    task = task_manager.get_task(task_id)
    if not task:
        return True
    if str(task.get("status")) == "canceled":
        return True
    return bool((task.get("data") or {}).get("cancel_requested"))


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

    try:
        if _is_cancel_requested(task_id):
            return

        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=15.0,
            message="正在读取方言数据并构建聚类输入",
        )

        result = build_cluster_result(snapshot, dialects_db=dialects_db)
        if _is_cancel_requested(task_id):
            return

        task_manager.update_task(
            task_id,
            progress=90.0,
            message="正在写入聚类结果",
        )
        result_path = _write_result(task_id, result)

        task_manager.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100.0,
            message="聚类任务已完成",
            data={
                "result_path": str(result_path),
                "summary": build_task_summary(snapshot, result=result),
            },
        )
    except Exception as exc:
        logger.exception("cluster job failed: %s", exc)
        if _is_cancel_requested(task_id):
            task_manager.update_task(
                task_id,
                status="canceled",
                message="聚类任务已取消",
            )
            return
        task_manager.update_task(
            task_id,
            status=TaskStatus.FAILED,
            error=str(exc),
            message=f"聚类任务失败: {exc}",
        )
