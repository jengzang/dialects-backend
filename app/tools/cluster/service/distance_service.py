"""
Cluster phoneme-distance modeling services.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
try:
    from numba import njit, prange
    from numba.typed import List as NumbaList
    NUMBA_AVAILABLE = True
except Exception:  # pragma: no cover - optional accelerator
    def njit(*args, **kwargs):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator
    prange = range
    NumbaList = None
    NUMBA_AVAILABLE = False

from app.tools.cluster.config import (
    DEFAULT_ANCHOR_WEIGHT,
    DEFAULT_SHARED_IDENTITY_WEIGHT,
    DIST_EPSILON,
    FEATURE_COLUMN_MAP,
    INTRA_CORR_WEIGHT,
    INTRA_STRUCT_WEIGHT,
)
from app.tools.cluster.utils import dedupe


@njit(cache=True)
def _compute_intra_group_distance_numba(
    token_ids_a: np.ndarray,
    token_ids_b: np.ndarray,
    token_count: int,
) -> float:
    shared_total = 0
    for index in range(token_ids_a.shape[0]):
        if token_ids_a[index] >= 0 and token_ids_b[index] >= 0:
            shared_total += 1
    if shared_total <= 0:
        return INTRA_CORR_WEIGHT

    map_x = np.full(token_count, -1, dtype=np.int32)
    map_y = np.full(token_count, -1, dtype=np.int32)
    inverse_x = np.empty(shared_total, dtype=np.int32)
    inverse_y = np.empty(shared_total, dtype=np.int32)

    size_x = 0
    size_y = 0
    position = 0
    for index in range(token_ids_a.shape[0]):
        token_a = token_ids_a[index]
        token_b = token_ids_b[index]
        if token_a < 0 or token_b < 0:
            continue

        slot_x = map_x[token_a]
        if slot_x < 0:
            slot_x = size_x
            map_x[token_a] = slot_x
            size_x += 1

        slot_y = map_y[token_b]
        if slot_y < 0:
            slot_y = size_y
            map_y[token_b] = slot_y
            size_y += 1

        inverse_x[position] = slot_x
        inverse_y[position] = slot_y
        position += 1

    count_x = np.zeros(size_x, dtype=np.int32)
    count_y = np.zeros(size_y, dtype=np.int32)
    count_xy = np.zeros(size_x * size_y, dtype=np.int32)
    for index in range(shared_total):
        slot_x = inverse_x[index]
        slot_y = inverse_y[index]
        count_x[slot_x] += 1
        count_y[slot_y] += 1
        count_xy[slot_x * size_y + slot_y] += 1

    h_y_given_x = 0.0
    h_x_given_y = 0.0
    same_both = 0.0
    for slot_x in range(size_x):
        for slot_y in range(size_y):
            freq = count_xy[slot_x * size_y + slot_y]
            if freq <= 0:
                continue
            prob_xy = freq / float(shared_total)
            prob_y_given_x = freq / float(count_x[slot_x])
            prob_x_given_y = freq / float(count_y[slot_y])
            h_y_given_x -= prob_xy * math.log(prob_y_given_x + DIST_EPSILON)
            h_x_given_y -= prob_xy * math.log(prob_x_given_y + DIST_EPSILON)
            same_both += freq * (freq - 1.0) / 2.0

    normalizer = math.log(max(size_x, size_y, 2))
    if normalizer <= 0.0:
        d_corr = 0.0
    else:
        d_corr = 0.5 * (h_y_given_x + h_x_given_y) / normalizer
        if d_corr < 0.0:
            d_corr = 0.0
        elif d_corr > 1.0:
            d_corr = 1.0

    if shared_total < 2:
        d_struct = 0.0
    else:
        total_pairs = shared_total * (shared_total - 1.0) / 2.0
        same_a = 0.0
        same_b = 0.0
        for slot_x in range(size_x):
            freq = count_x[slot_x]
            same_a += freq * (freq - 1.0) / 2.0
        for slot_y in range(size_y):
            freq = count_y[slot_y]
            same_b += freq * (freq - 1.0) / 2.0
        mismatch = same_a + same_b - 2.0 * same_both
        d_struct = mismatch / total_pairs if total_pairs > 0.0 else 0.0
        if d_struct < 0.0:
            d_struct = 0.0
        elif d_struct > 1.0:
            d_struct = 1.0

    return INTRA_CORR_WEIGHT * d_corr + INTRA_STRUCT_WEIGHT * d_struct


@njit(cache=True)
def _build_alignment_model_numba(
    token_ids_a: np.ndarray,
    token_ids_b: np.ndarray,
    token_count: int,
):
    shared_total = 0
    used_x = np.zeros(token_count, dtype=np.uint8)
    used_y = np.zeros(token_count, dtype=np.uint8)
    for index in range(token_ids_a.shape[0]):
        if token_ids_a[index] >= 0 and token_ids_b[index] >= 0:
            shared_total += 1
            used_x[token_ids_a[index]] = 1
            used_y[token_ids_b[index]] = 1

    lookup_x = np.full(token_count, -1, dtype=np.int32)
    lookup_y = np.full(token_count, -1, dtype=np.int32)
    if shared_total <= 0:
        return (
            np.zeros((0, 0), dtype=np.int32),
            np.zeros(0, dtype=np.int32),
            np.zeros(0, dtype=np.int32),
            lookup_x,
            lookup_y,
        )

    size_x = 0
    size_y = 0
    for token_id in range(token_count):
        if used_x[token_id] == 1:
            lookup_x[token_id] = size_x
            size_x += 1
        if used_y[token_id] == 1:
            lookup_y[token_id] = size_y
            size_y += 1

    count_x = np.zeros(size_x, dtype=np.int32)
    count_y = np.zeros(size_y, dtype=np.int32)
    count_xy = np.zeros((size_x, size_y), dtype=np.int32)
    for index in range(token_ids_a.shape[0]):
        token_a = token_ids_a[index]
        token_b = token_ids_b[index]
        if token_a < 0 or token_b < 0:
            continue
        slot_x = lookup_x[token_a]
        slot_y = lookup_y[token_b]
        count_x[slot_x] += 1
        count_y[slot_y] += 1
        count_xy[slot_x, slot_y] += 1

    return count_xy, count_x, count_y, lookup_x, lookup_y


@njit(cache=True)
def _conditional_entropy_distance_with_model_numba(
    token_ids_a: np.ndarray,
    token_ids_b: np.ndarray,
    model_count_xy: np.ndarray,
    model_count_x: np.ndarray,
    model_count_y: np.ndarray,
    model_lookup_x: np.ndarray,
    model_lookup_y: np.ndarray,
) -> float:
    total = 0
    for index in range(token_ids_a.shape[0]):
        if token_ids_a[index] >= 0 and token_ids_b[index] >= 0:
            total += 1
    if total <= 0:
        return 1.0

    normalizer = math.log(max(model_count_x.shape[0], model_count_y.shape[0], 2))
    if normalizer <= 0.0:
        return 0.0

    inv_total = 1.0 / float(total)
    h_y_given_x = 0.0
    h_x_given_y = 0.0
    for index in range(token_ids_a.shape[0]):
        token_a = token_ids_a[index]
        token_b = token_ids_b[index]
        if token_a < 0 or token_b < 0:
            continue

        row = -1
        col = -1
        if token_a < model_lookup_x.shape[0]:
            row = model_lookup_x[token_a]
        if token_b < model_lookup_y.shape[0]:
            col = model_lookup_y[token_b]

        prob_y_given_x = 0.0
        prob_x_given_y = 0.0
        if row >= 0 and col >= 0:
            freq = float(model_count_xy[row, col])
            if model_count_x[row] > 0:
                prob_y_given_x = freq / float(model_count_x[row])
            if model_count_y[col] > 0:
                prob_x_given_y = freq / float(model_count_y[col])
        h_y_given_x -= inv_total * math.log(prob_y_given_x + DIST_EPSILON)
        h_x_given_y -= inv_total * math.log(prob_x_given_y + DIST_EPSILON)

    value = 0.5 * (h_y_given_x + h_x_given_y) / normalizer
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@njit(cache=True)
def _compute_group_distance_anchored_numba(
    token_ids_a: np.ndarray,
    token_ids_b: np.ndarray,
    token_count: int,
    signatures_a: np.ndarray,
    signatures_b: np.ndarray,
    anchor_weight: float,
) -> float:
    count_xy, count_x, count_y, lookup_x, lookup_y = _build_alignment_model_numba(
        token_ids_a,
        token_ids_b,
        token_count,
    )
    shared_total = int(np.sum(count_x))
    if shared_total <= 0:
        return ((1.0 - anchor_weight) * INTRA_CORR_WEIGHT) + anchor_weight

    size_x = count_x.shape[0]
    size_y = count_y.shape[0]
    slot_token_x = np.empty(size_x, dtype=np.int32)
    slot_token_y = np.empty(size_y, dtype=np.int32)
    for token_id in range(token_count):
        slot_x = lookup_x[token_id]
        if slot_x >= 0:
            slot_token_x[slot_x] = token_id
        slot_y = lookup_y[token_id]
        if slot_y >= 0:
            slot_token_y[slot_y] = token_id

    h_y_given_x = 0.0
    h_x_given_y = 0.0
    same_both = 0.0
    for slot_x in range(size_x):
        for slot_y in range(size_y):
            freq = count_xy[slot_x, slot_y]
            if freq <= 0:
                continue
            prob_xy = freq / float(shared_total)
            prob_y_given_x = freq / float(count_x[slot_x])
            prob_x_given_y = freq / float(count_y[slot_y])
            h_y_given_x -= prob_xy * math.log(prob_y_given_x + DIST_EPSILON)
            h_x_given_y -= prob_xy * math.log(prob_x_given_y + DIST_EPSILON)
            same_both += freq * (freq - 1.0) / 2.0

    normalizer = math.log(max(size_x, size_y, 2))
    if normalizer <= 0.0:
        d_corr = 0.0
    else:
        d_corr = 0.5 * (h_y_given_x + h_x_given_y) / normalizer
        if d_corr < 0.0:
            d_corr = 0.0
        elif d_corr > 1.0:
            d_corr = 1.0

    if shared_total < 2:
        d_struct = 0.0
    else:
        total_pairs = shared_total * (shared_total - 1.0) / 2.0
        same_a = 0.0
        same_b = 0.0
        for slot_x in range(size_x):
            freq = count_x[slot_x]
            same_a += freq * (freq - 1.0) / 2.0
        for slot_y in range(size_y):
            freq = count_y[slot_y]
            same_b += freq * (freq - 1.0) / 2.0
        mismatch = same_a + same_b - 2.0 * same_both
        d_struct = mismatch / total_pairs if total_pairs > 0.0 else 0.0
        if d_struct < 0.0:
            d_struct = 0.0
        elif d_struct > 1.0:
            d_struct = 1.0

    d_intra = INTRA_CORR_WEIGHT * d_corr + INTRA_STRUCT_WEIGHT * d_struct

    inv_total_x = 1.0 / float(np.sum(count_x))
    inv_total_y = 1.0 / float(np.sum(count_y))
    dist_a_to_b = 0.0
    for slot_x in range(size_x):
        best_slot_y = -1
        best_freq = -1
        for slot_y in range(size_y):
            freq = count_xy[slot_x, slot_y]
            if freq > best_freq:
                best_freq = freq
                best_slot_y = slot_y
        if best_slot_y < 0:
            dist_a_to_b += count_x[slot_x] * inv_total_x
            continue
        token_a = slot_token_x[slot_x]
        token_b = slot_token_y[best_slot_y]
        diff0 = signatures_a[token_a, 0] - signatures_b[token_b, 0]
        diff1 = signatures_a[token_a, 1] - signatures_b[token_b, 1]
        value = math.sqrt(diff0 * diff0 + diff1 * diff1) / math.sqrt(2.0)
        if value < 0.0:
            value = 0.0
        elif value > 1.0:
            value = 1.0
        dist_a_to_b += (count_x[slot_x] * inv_total_x) * value

    dist_b_to_a = 0.0
    for slot_y in range(size_y):
        best_slot_x = -1
        best_freq = -1
        for slot_x in range(size_x):
            freq = count_xy[slot_x, slot_y]
            if freq > best_freq:
                best_freq = freq
                best_slot_x = slot_x
        if best_slot_x < 0:
            dist_b_to_a += count_y[slot_y] * inv_total_y
            continue
        token_b = slot_token_y[slot_y]
        token_a = slot_token_x[best_slot_x]
        diff0 = signatures_b[token_b, 0] - signatures_a[token_a, 0]
        diff1 = signatures_b[token_b, 1] - signatures_a[token_a, 1]
        value = math.sqrt(diff0 * diff0 + diff1 * diff1) / math.sqrt(2.0)
        if value < 0.0:
            value = 0.0
        elif value > 1.0:
            value = 1.0
        dist_b_to_a += (count_y[slot_y] * inv_total_y) * value

    d_anchor = 0.5 * (dist_a_to_b + dist_b_to_a)
    return ((1.0 - anchor_weight) * d_intra) + (anchor_weight * d_anchor)


@njit(cache=True, parallel=True)
def _build_total_distance_matrix_intra_group_numba(
    token_matrices,
    present_count_matrices,
    token_counts: np.ndarray,
    group_weights: np.ndarray,
) -> np.ndarray:
    group_count = len(token_matrices)
    size = present_count_matrices[0].shape[0]
    matrix = np.zeros((size, size), dtype=np.float64)
    for i in prange(size):
        for j in range(i + 1, size):
            total = 0.0
            weight_sum = 0.0
            for group_index in range(group_count):
                present_count_a = present_count_matrices[group_index][i]
                present_count_b = present_count_matrices[group_index][j]
                if present_count_a == 0 and present_count_b == 0:
                    continue

                weight = group_weights[group_index]
                weight_sum += weight
                if present_count_a == 0 or present_count_b == 0:
                    total += weight
                    continue

                total += weight * _compute_intra_group_distance_numba(
                    token_matrices[group_index][i],
                    token_matrices[group_index][j],
                    int(token_counts[group_index]),
                )

            distance = total / weight_sum if weight_sum > 0.0 else 1.0
            matrix[i, j] = distance
            matrix[j, i] = distance
    return matrix


@njit(cache=True, parallel=True)
def _build_total_distance_matrix_anchored_numba(
    token_matrices,
    present_count_matrices,
    token_counts: np.ndarray,
    group_weights: np.ndarray,
    anchor_signatures,
    anchor_weight: float,
) -> np.ndarray:
    group_count = len(token_matrices)
    size = present_count_matrices[0].shape[0]
    matrix = np.zeros((size, size), dtype=np.float64)
    for i in prange(size):
        for j in range(i + 1, size):
            total = 0.0
            weight_sum = 0.0
            for group_index in range(group_count):
                present_count_a = present_count_matrices[group_index][i]
                present_count_b = present_count_matrices[group_index][j]
                if present_count_a == 0 and present_count_b == 0:
                    continue

                weight = group_weights[group_index]
                weight_sum += weight
                if present_count_a == 0 or present_count_b == 0:
                    total += weight
                    continue

                total += weight * _compute_group_distance_anchored_numba(
                    token_matrices[group_index][i],
                    token_matrices[group_index][j],
                    int(token_counts[group_index]),
                    anchor_signatures[group_index][i],
                    anchor_signatures[group_index][j],
                    anchor_weight,
                )

            distance = total / weight_sum if weight_sum > 0.0 else 1.0
            matrix[i, j] = distance
            matrix[j, i] = distance
    return matrix


@njit(cache=True, parallel=True)
def _build_total_distance_matrix_shared_multi_dim_numba(
    token_matrices,
    present_count_matrices,
    token_counts: np.ndarray,
    group_weights: np.ndarray,
    group_dimension_ids: np.ndarray,
    bucket_initial_matrix: np.ndarray,
    bucket_initial_count: int,
    bucket_final_matrix: np.ndarray,
    bucket_final_count: int,
    bucket_tone_matrix: np.ndarray,
    bucket_tone_count: int,
    shared_identity_weight: float,
) -> np.ndarray:
    group_count = len(token_matrices)
    size = present_count_matrices[0].shape[0]
    matrix = np.zeros((size, size), dtype=np.float64)
    for i in prange(size):
        for j in range(i + 1, size):
            (
                initial_count_xy,
                initial_count_x,
                initial_count_y,
                initial_lookup_x,
                initial_lookup_y,
            ) = _build_alignment_model_numba(
                bucket_initial_matrix[i],
                bucket_initial_matrix[j],
                bucket_initial_count,
            )
            (
                final_count_xy,
                final_count_x,
                final_count_y,
                final_lookup_x,
                final_lookup_y,
            ) = _build_alignment_model_numba(
                bucket_final_matrix[i],
                bucket_final_matrix[j],
                bucket_final_count,
            )
            (
                tone_count_xy,
                tone_count_x,
                tone_count_y,
                tone_lookup_x,
                tone_lookup_y,
            ) = _build_alignment_model_numba(
                bucket_tone_matrix[i],
                bucket_tone_matrix[j],
                bucket_tone_count,
            )
            total = 0.0
            weight_sum = 0.0
            for group_index in range(group_count):
                present_count_a = present_count_matrices[group_index][i]
                present_count_b = present_count_matrices[group_index][j]
                if present_count_a == 0 and present_count_b == 0:
                    continue

                weight = group_weights[group_index]
                weight_sum += weight
                if present_count_a == 0 or present_count_b == 0:
                    total += weight
                    continue

                d_intra = _compute_intra_group_distance_numba(
                    token_matrices[group_index][i],
                    token_matrices[group_index][j],
                    int(token_counts[group_index]),
                )
                model_count_xy = final_count_xy
                model_count_x = final_count_x
                model_count_y = final_count_y
                model_lookup_x = final_lookup_x
                model_lookup_y = final_lookup_y
                dimension_id = int(group_dimension_ids[group_index])
                if dimension_id == 0:
                    model_count_xy = initial_count_xy
                    model_count_x = initial_count_x
                    model_count_y = initial_count_y
                    model_lookup_x = initial_lookup_x
                    model_lookup_y = initial_lookup_y
                elif dimension_id == 2:
                    model_count_xy = tone_count_xy
                    model_count_x = tone_count_x
                    model_count_y = tone_count_y
                    model_lookup_x = tone_lookup_x
                    model_lookup_y = tone_lookup_y
                d_shared = _conditional_entropy_distance_with_model_numba(
                    token_matrices[group_index][i],
                    token_matrices[group_index][j],
                    model_count_xy,
                    model_count_x,
                    model_count_y,
                    model_lookup_x,
                    model_lookup_y,
                )
                total += weight * (
                    ((1.0 - shared_identity_weight) * d_intra)
                    + (shared_identity_weight * d_shared)
                )

            distance = total / weight_sum if weight_sum > 0.0 else 1.0
            matrix[i, j] = distance
            matrix[j, i] = distance
    return matrix


def build_dimension_token_catalogs(
    groups: Sequence[Dict[str, Any]],
    dialect_data: Dict[str, Dict[str, Dict[str, set[str]]]],
) -> Dict[str, Dict[str, Any]]:
    dimensions = sorted({group["compare_dimension"] for group in groups})
    tokens_by_dimension: Dict[str, set[str]] = {dimension: set() for dimension in dimensions}

    for location_char_data in dialect_data.values():
        for char_data in location_char_data.values():
            for dimension in dimensions:
                values = set(char_data.get(dimension, set()))
                if not values:
                    continue
                normalized_values = sorted(value for value in values if value)
                if normalized_values:
                    tokens_by_dimension[dimension].add("|".join(normalized_values))

    catalogs: Dict[str, Dict[str, Any]] = {}
    for dimension, tokens in tokens_by_dimension.items():
        ordered_tokens = tuple(sorted(tokens))
        token_parts = tuple(
            tuple(part for part in token.split("|") if part)
            for token in ordered_tokens
        )
        token_value_sets = tuple(frozenset(parts) for parts in token_parts)
        catalogs[dimension] = {
            "tokens": ordered_tokens,
            "token_parts": token_parts,
            "token_value_sets": token_value_sets,
            "token_to_id": {token: index for index, token in enumerate(ordered_tokens)},
            "value_distance_cache": {},
        }
    return catalogs


def build_group_model(
    group: Dict[str, Any],
    locations: Sequence[str],
    dialect_data: Dict[str, Dict[str, Dict[str, set[str]]]],
    dimension_catalog: Dict[str, Any],
) -> Dict[str, Any]:
    dimension = group["compare_dimension"]
    resolved_chars = list(group["resolved_chars"])
    char_count = len(resolved_chars)
    token_to_id = dimension_catalog["token_to_id"]
    location_models: Dict[str, Dict[str, Any]] = {}
    token_matrix = np.full((len(locations), char_count), -1, dtype=np.int32)
    present_char_counts = np.zeros(len(locations), dtype=np.int32)

    for location_index, location in enumerate(locations):
        location_char_data = dialect_data.get(location, {})
        present_char_count = 0

        for index, char in enumerate(resolved_chars):
            values = set(location_char_data.get(char, {}).get(dimension, set()))
            if not values:
                continue

            normalized_values = sorted(value for value in values if value)
            if not normalized_values:
                continue

            present_char_count += 1
            token_matrix[location_index, index] = token_to_id["|".join(normalized_values)]

        present_char_counts[location_index] = present_char_count
        location_models[location] = {
            "token_ids": token_matrix[location_index],
            "present_char_count": present_char_count,
            "coverage": (
                float(present_char_count / char_count)
                if char_count
                else 0.0
            ),
        }

    effective_locations = [
        location
        for location in locations
        if location_models[location]["present_char_count"] > 0
    ]
    warnings: List[str] = []
    if not effective_locations:
        warnings.append("该组在所有地点上都没有有效读音数据")
    elif len(effective_locations) < len(locations):
        warnings.append(
            f"该组仅在 {len(effective_locations)}/{len(locations)} 个地点有有效读音覆盖"
        )
    if char_count < 2:
        warnings.append("该组字数少于 2，同音结构特征会退化")

    return {
        **group,
        "token_catalog": dimension_catalog,
        "locations": location_models,
        "token_matrix": token_matrix,
        "present_char_counts": present_char_counts,
        "effective_locations": effective_locations,
        "coverage_ratio": (
            float(len(effective_locations) / len(locations)) if locations else 0.0
        ),
        "warnings": warnings,
    }


def build_alignment_info(
    token_ids_a: np.ndarray,
    token_ids_b: np.ndarray,
    include_lookup: bool = False,
) -> Dict[str, Any]:
    shared_mask = (token_ids_a >= 0) & (token_ids_b >= 0)
    total = int(np.count_nonzero(shared_mask))
    if total <= 0:
        return {
            "count_xy": np.zeros((0, 0), dtype=np.int32),
            "count_x": np.zeros(0, dtype=np.int32),
            "count_y": np.zeros(0, dtype=np.int32),
            "token_ids_x": np.zeros(0, dtype=np.int32),
            "token_ids_y": np.zeros(0, dtype=np.int32),
            "total": 0,
            "map_a_to_b": np.zeros(0, dtype=np.int32),
            "map_b_to_a": np.zeros(0, dtype=np.int32),
            "index_x": {} if include_lookup else None,
            "index_y": {} if include_lookup else None,
        }

    shared_x = token_ids_a[shared_mask]
    shared_y = token_ids_b[shared_mask]
    token_ids_x, inverse_x = np.unique(shared_x, return_inverse=True)
    token_ids_y, inverse_y = np.unique(shared_y, return_inverse=True)

    count_x = np.bincount(inverse_x, minlength=token_ids_x.size).astype(np.int32)
    count_y = np.bincount(inverse_y, minlength=token_ids_y.size).astype(np.int32)

    pair_codes = inverse_x * token_ids_y.size + inverse_y
    count_xy = np.bincount(
        pair_codes,
        minlength=token_ids_x.size * token_ids_y.size,
    ).reshape(token_ids_x.size, token_ids_y.size).astype(np.int32)

    map_a_to_b = token_ids_y[count_xy.argmax(axis=1)] if token_ids_x.size else np.zeros(0, dtype=np.int32)
    map_b_to_a = token_ids_x[count_xy.argmax(axis=0)] if token_ids_y.size else np.zeros(0, dtype=np.int32)

    return {
        "count_xy": count_xy,
        "count_x": count_x,
        "count_y": count_y,
        "token_ids_x": token_ids_x.astype(np.int32, copy=False),
        "token_ids_y": token_ids_y.astype(np.int32, copy=False),
        "total": total,
        "map_a_to_b": map_a_to_b.astype(np.int32, copy=False),
        "map_b_to_a": map_b_to_a.astype(np.int32, copy=False),
        "index_x": (
            {int(token_id): index for index, token_id in enumerate(token_ids_x.tolist())}
            if include_lookup
            else None
        ),
        "index_y": (
            {int(token_id): index for index, token_id in enumerate(token_ids_y.tolist())}
            if include_lookup
            else None
        ),
    }


def conditional_entropy_distance_from_counts(
    count_xy: np.ndarray,
    count_x: np.ndarray,
    count_y: np.ndarray,
    total: int,
) -> float:
    if total <= 0:
        return 1.0

    nz_x, nz_y = np.nonzero(count_xy)
    if nz_x.size == 0:
        return 1.0

    freq = count_xy[nz_x, nz_y].astype(float)
    prob_xy = freq / float(total)
    prob_y_given_x = freq / count_x[nz_x].astype(float)
    prob_x_given_y = freq / count_y[nz_y].astype(float)

    h_y_given_x = float(-np.sum(prob_xy * np.log(prob_y_given_x + DIST_EPSILON)))
    h_x_given_y = float(-np.sum(prob_xy * np.log(prob_x_given_y + DIST_EPSILON)))

    normalizer = math.log(max(int(count_x.size), int(count_y.size), 2))
    if normalizer <= 0:
        return 0.0
    return min(1.0, max(0.0, 0.5 * (h_y_given_x + h_x_given_y) / normalizer))


def pair_relation_distance_from_counts(
    count_xy: np.ndarray,
    count_x: np.ndarray,
    count_y: np.ndarray,
    total: int,
) -> float:
    if total < 2:
        return 0.0

    total_pairs = total * (total - 1) / 2.0
    if total_pairs <= 0:
        return 0.0

    count_x_f = count_x.astype(float)
    count_y_f = count_y.astype(float)
    count_xy_f = count_xy.astype(float)
    same_a = float(np.sum(count_x_f * (count_x_f - 1.0) / 2.0))
    same_b = float(np.sum(count_y_f * (count_y_f - 1.0) / 2.0))
    same_both = float(np.sum(count_xy_f * (count_xy_f - 1.0) / 2.0))
    mismatch = same_a + same_b - 2.0 * same_both
    return min(1.0, max(0.0, float(mismatch / total_pairs)))


def conditional_entropy_distance_with_model(
    token_ids_a: np.ndarray,
    token_ids_b: np.ndarray,
    model_alignment: Dict[str, Any],
) -> float:
    shared_mask = (token_ids_a >= 0) & (token_ids_b >= 0)
    total = int(np.count_nonzero(shared_mask))
    if total <= 0:
        return 1.0

    model_count_x = model_alignment["count_x"]
    model_count_y = model_alignment["count_y"]
    normalizer = math.log(max(int(model_count_x.size), int(model_count_y.size), 2))
    if normalizer <= 0:
        return 0.0

    shared_x = token_ids_a[shared_mask]
    shared_y = token_ids_b[shared_mask]
    index_x = model_alignment["index_x"] or {}
    index_y = model_alignment["index_y"] or {}
    row_indices = np.asarray(
        [index_x.get(int(token_id), -1) for token_id in shared_x],
        dtype=np.int32,
    )
    col_indices = np.asarray(
        [index_y.get(int(token_id), -1) for token_id in shared_y],
        dtype=np.int32,
    )

    prob_y_given_x = np.zeros(total, dtype=float)
    prob_x_given_y = np.zeros(total, dtype=float)
    valid = (row_indices >= 0) & (col_indices >= 0)
    if np.any(valid):
        valid_rows = row_indices[valid]
        valid_cols = col_indices[valid]
        freq = model_alignment["count_xy"][valid_rows, valid_cols].astype(float)
        prob_y_given_x[valid] = freq / np.maximum(model_count_x[valid_rows], 1).astype(float)
        prob_x_given_y[valid] = freq / np.maximum(model_count_y[valid_cols], 1).astype(float)

    weight = 1.0 / float(total)
    h_y_given_x = float(-np.sum(weight * np.log(prob_y_given_x + DIST_EPSILON)))
    h_x_given_y = float(-np.sum(weight * np.log(prob_x_given_y + DIST_EPSILON)))
    return min(1.0, max(0.0, 0.5 * (h_y_given_x + h_x_given_y) / normalizer))


def token_value_distance_by_id(
    token_id_a: int,
    token_id_b: int,
    token_catalog: Dict[str, Any],
) -> float:
    cache_key = (
        (token_id_a, token_id_b)
        if token_id_a <= token_id_b
        else (token_id_b, token_id_a)
    )
    cache = token_catalog["value_distance_cache"]
    if cache_key in cache:
        return cache[cache_key]

    values_a = token_catalog["token_value_sets"][token_id_a]
    values_b = token_catalog["token_value_sets"][token_id_b]
    union = values_a | values_b
    if not union:
        distance = 0.0
    else:
        intersection = values_a & values_b
        distance = 1.0 - (len(intersection) / len(union))
    cache[cache_key] = float(distance)
    return float(distance)


def aligned_value_distance(
    count_x: np.ndarray,
    count_y: np.ndarray,
    token_ids_x: np.ndarray,
    token_ids_y: np.ndarray,
    map_a_to_b: np.ndarray,
    map_b_to_a: np.ndarray,
    token_catalog: Dict[str, Any],
) -> float:
    total_x = float(np.sum(count_x))
    total_y = float(np.sum(count_y))
    if total_x <= 0 or total_y <= 0:
        return 1.0

    dist_a_to_b = 0.0
    for token_id, freq, mapped_token_id in zip(token_ids_x, count_x, map_a_to_b):
        if int(mapped_token_id) < 0:
            dist_a_to_b += float(freq) / total_x
            continue
        dist_a_to_b += (float(freq) / total_x) * token_value_distance_by_id(
            int(token_id),
            int(mapped_token_id),
            token_catalog,
        )

    dist_b_to_a = 0.0
    for token_id, freq, mapped_token_id in zip(token_ids_y, count_y, map_b_to_a):
        if int(mapped_token_id) < 0:
            dist_b_to_a += float(freq) / total_y
            continue
        dist_b_to_a += (float(freq) / total_y) * token_value_distance_by_id(
            int(mapped_token_id),
            int(token_id),
            token_catalog,
        )

    return min(1.0, max(0.0, 0.5 * (dist_a_to_b + dist_b_to_a)))


def token_anchor_signature_by_id(
    token_id: int,
    inventory_profile: Dict[str, Dict[str, float]],
    token_catalog: Dict[str, Any],
    cache: Optional[Dict[Tuple[int, int], np.ndarray]] = None,
    cache_key: Optional[Tuple[int, int]] = None,
) -> np.ndarray:
    if cache is not None and cache_key is not None and cache_key in cache:
        return cache[cache_key]

    parts = token_catalog["token_parts"][token_id]
    if not parts:
        signature = np.zeros(2, dtype=float)
    else:
        shares: List[float] = []
        ranks: List[float] = []
        for value in parts:
            stats = inventory_profile.get(value)
            if not stats:
                continue
            shares.append(float(stats.get("share", 0.0)))
            ranks.append(float(stats.get("rank_pct", 1.0)))
        if shares:
            signature = np.asarray(
                [
                    float(sum(shares) / len(shares)),
                    float(sum(ranks) / len(ranks)),
                ],
                dtype=float,
            )
        else:
            signature = np.zeros(2, dtype=float)

    if cache is not None and cache_key is not None:
        cache[cache_key] = signature
    return signature


def project_model_mapping(
    token_ids: np.ndarray,
    model_index: Optional[Dict[int, int]],
    model_mapping: np.ndarray,
) -> np.ndarray:
    if token_ids.size == 0:
        return np.zeros(0, dtype=np.int32)
    if not model_index:
        return np.full(token_ids.size, -1, dtype=np.int32)

    projected = np.full(token_ids.size, -1, dtype=np.int32)
    for index, token_id in enumerate(token_ids.tolist()):
        model_pos = model_index.get(int(token_id))
        if model_pos is not None:
            projected[index] = int(model_mapping[model_pos])
    return projected


def anchor_distance(
    count_x: np.ndarray,
    count_y: np.ndarray,
    token_ids_x: np.ndarray,
    token_ids_y: np.ndarray,
    map_a_to_b: np.ndarray,
    map_b_to_a: np.ndarray,
    inventory_profile_a: Dict[str, Dict[str, float]],
    inventory_profile_b: Dict[str, Dict[str, float]],
    token_catalog: Dict[str, Any],
    signature_cache: Optional[Dict[Tuple[int, int], np.ndarray]] = None,
) -> float:
    total_x = float(np.sum(count_x))
    total_y = float(np.sum(count_y))
    if total_x <= 0 or total_y <= 0:
        return 1.0

    def weighted_distance(
        source_counts: np.ndarray,
        source_token_ids: np.ndarray,
        matched_token_ids: np.ndarray,
        source_profile: Dict[str, Dict[str, float]],
        target_profile: Dict[str, Dict[str, float]],
        total: float,
        source_location_key: int,
        target_location_key: int,
    ) -> float:
        value = 0.0
        for token_id, freq, matched_token_id in zip(source_token_ids, source_counts, matched_token_ids):
            if int(matched_token_id) < 0:
                value += float(freq) / total
                continue
            source_sig = token_anchor_signature_by_id(
                int(token_id),
                source_profile,
                token_catalog,
                cache=signature_cache,
                cache_key=(source_location_key, int(token_id)),
            )
            target_sig = token_anchor_signature_by_id(
                int(matched_token_id),
                target_profile,
                token_catalog,
                cache=signature_cache,
                cache_key=(target_location_key, int(matched_token_id)),
            )
            diff = source_sig - target_sig
            value += (float(freq) / total) * min(
                1.0,
                max(0.0, float(np.linalg.norm(diff) / math.sqrt(max(diff.size, 1)))),
            )
        return value

    dist_a = weighted_distance(
        count_x,
        token_ids_x,
        map_a_to_b,
        inventory_profile_a,
        inventory_profile_b,
        total_x,
        id(inventory_profile_a),
        id(inventory_profile_b),
    )
    dist_b = weighted_distance(
        count_y,
        token_ids_y,
        map_b_to_a,
        inventory_profile_b,
        inventory_profile_a,
        total_y,
        id(inventory_profile_b),
        id(inventory_profile_a),
    )
    return min(1.0, max(0.0, 0.5 * (dist_a + dist_b)))


def build_dimension_bucket_models(
    groups: Sequence[Dict[str, Any]],
    locations: Sequence[str],
    dialect_data: Dict[str, Dict[str, Dict[str, set[str]]]],
    dimension_catalogs: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    bucket_models: Dict[str, Dict[str, Any]] = {}
    for dimension in sorted({group["compare_dimension"] for group in groups}):
        union_chars = dedupe(
            char
            for group in groups
            if group["compare_dimension"] == dimension
            for char in group["resolved_chars"]
        )
        synthetic_group = {
            "label": f"bucket_{dimension}",
            "source_mode": "derived",
            "table_name": "characters",
            "compare_dimension": dimension,
            "feature_column": FEATURE_COLUMN_MAP[dimension],
            "group_weight": 1.0,
            "use_phonetic_values": False,
            "phonetic_value_weight": 0.0,
            "resolved_chars": union_chars,
            "char_count": len(union_chars),
            "sample_chars": union_chars[:12],
            "cache_hit": False,
            "cache_key": None,
            "resolver": "dimension_bucket",
            "query_labels": [],
        }
        bucket_models[dimension] = build_group_model(
            synthetic_group,
            locations,
            dialect_data,
            dimension_catalogs[dimension],
        )
    return bucket_models


def build_anchor_signature_matrices(
    dimensions: Sequence[str],
    locations: Sequence[str],
    inventory_profiles: Dict[str, Dict[str, Dict[str, Dict[str, float]]]],
    dimension_catalogs: Dict[str, Dict[str, Any]],
) -> Dict[str, np.ndarray]:
    signature_matrices: Dict[str, np.ndarray] = {}
    for dimension in dimensions:
        token_catalog = dimension_catalogs[dimension]
        token_count = len(token_catalog["tokens"])
        matrix = np.zeros((len(locations), token_count, 2), dtype=np.float64)
        for location_index, location in enumerate(locations):
            inventory_profile = inventory_profiles.get(location, {}).get(dimension, {})
            for token_id in range(token_count):
                signature = token_anchor_signature_by_id(
                    token_id,
                    inventory_profile,
                    token_catalog,
                )
                matrix[location_index, token_id, 0] = float(signature[0])
                matrix[location_index, token_id, 1] = float(signature[1])
        signature_matrices[dimension] = matrix
    return signature_matrices


def build_shared_bucket_matrix_inputs(
    locations: Sequence[str],
    bucket_models: Dict[str, Dict[str, Any]],
) -> Tuple[
    np.ndarray,
    int,
    np.ndarray,
    int,
    np.ndarray,
    int,
]:
    empty_matrix = np.full((len(locations), 0), -1, dtype=np.int32)

    def resolve_dimension(dimension: str) -> Tuple[np.ndarray, int]:
        bucket_model = bucket_models.get(dimension)
        if bucket_model is None:
            return empty_matrix, 0
        return (
            bucket_model["token_matrix"],
            len(bucket_model["token_catalog"]["tokens"]),
        )

    initial_matrix, initial_count = resolve_dimension("initial")
    final_matrix, final_count = resolve_dimension("final")
    tone_matrix, tone_count = resolve_dimension("tone")
    return (
        initial_matrix,
        initial_count,
        final_matrix,
        final_count,
        tone_matrix,
        tone_count,
    )


def build_total_distance_matrix(
    group_models: Sequence[Dict[str, Any]],
    locations: Sequence[str],
    phoneme_mode: str,
    inventory_profiles: Dict[str, Dict[str, Dict[str, Dict[str, float]]]],
    bucket_models: Dict[str, Dict[str, Any]],
    force_python: bool = False,
    block_size: int = 64,
) -> Tuple[np.ndarray, Dict[str, float]]:
    size = len(locations)
    if (
        NUMBA_AVAILABLE
        and not force_python
        and phoneme_mode == "intra_group"
        and all(not bool(group["use_phonetic_values"]) for group in group_models)
    ):
        token_matrices = NumbaList()
        present_count_matrices = NumbaList()
        token_counts = np.empty(len(group_models), dtype=np.int32)
        group_weights = np.empty(len(group_models), dtype=np.float64)
        for group_index, group in enumerate(group_models):
            token_matrices.append(group["token_matrix"])
            present_count_matrices.append(group["present_char_counts"])
            token_counts[group_index] = len(group["token_catalog"]["tokens"])
            group_weights[group_index] = float(group["group_weight"])
        matrix = _build_total_distance_matrix_intra_group_numba(
            token_matrices,
            present_count_matrices,
            token_counts,
            group_weights,
        )
        return matrix, {
            "anchor_weight": DEFAULT_ANCHOR_WEIGHT,
            "shared_identity_weight": DEFAULT_SHARED_IDENTITY_WEIGHT,
        }

    if (
        NUMBA_AVAILABLE
        and not force_python
        and phoneme_mode == "anchored_inventory"
        and all(not bool(group["use_phonetic_values"]) for group in group_models)
    ):
        dimension_catalogs = {
            group["compare_dimension"]: group["token_catalog"] for group in group_models
        }
        signature_matrices = build_anchor_signature_matrices(
            dimensions=sorted({group["compare_dimension"] for group in group_models}),
            locations=locations,
            inventory_profiles=inventory_profiles,
            dimension_catalogs=dimension_catalogs,
        )
        token_matrices = NumbaList()
        present_count_matrices = NumbaList()
        anchor_signatures = NumbaList()
        token_counts = np.empty(len(group_models), dtype=np.int32)
        group_weights = np.empty(len(group_models), dtype=np.float64)
        for group_index, group in enumerate(group_models):
            token_matrices.append(group["token_matrix"])
            present_count_matrices.append(group["present_char_counts"])
            anchor_signatures.append(signature_matrices[group["compare_dimension"]])
            token_counts[group_index] = len(group["token_catalog"]["tokens"])
            group_weights[group_index] = float(group["group_weight"])
        matrix = _build_total_distance_matrix_anchored_numba(
            token_matrices,
            present_count_matrices,
            token_counts,
            group_weights,
            anchor_signatures,
            DEFAULT_ANCHOR_WEIGHT,
        )
        return matrix, {
            "anchor_weight": DEFAULT_ANCHOR_WEIGHT,
            "shared_identity_weight": DEFAULT_SHARED_IDENTITY_WEIGHT,
        }

    if (
        NUMBA_AVAILABLE
        and not force_python
        and phoneme_mode == "shared_request_identity"
        and all(not bool(group["use_phonetic_values"]) for group in group_models)
    ):
        token_matrices = NumbaList()
        present_count_matrices = NumbaList()
        token_counts = np.empty(len(group_models), dtype=np.int32)
        group_weights = np.empty(len(group_models), dtype=np.float64)
        group_dimension_ids = np.empty(len(group_models), dtype=np.int32)
        dimension_to_id = {"initial": 0, "final": 1, "tone": 2}
        for group_index, group in enumerate(group_models):
            token_matrices.append(group["token_matrix"])
            present_count_matrices.append(group["present_char_counts"])
            token_counts[group_index] = len(group["token_catalog"]["tokens"])
            group_weights[group_index] = float(group["group_weight"])
            group_dimension_ids[group_index] = dimension_to_id[group["compare_dimension"]]
        (
            bucket_initial_matrix,
            bucket_initial_count,
            bucket_final_matrix,
            bucket_final_count,
            bucket_tone_matrix,
            bucket_tone_count,
        ) = build_shared_bucket_matrix_inputs(locations, bucket_models)
        matrix = _build_total_distance_matrix_shared_multi_dim_numba(
            token_matrices,
            present_count_matrices,
            token_counts,
            group_weights,
            group_dimension_ids,
            bucket_initial_matrix,
            bucket_initial_count,
            bucket_final_matrix,
            bucket_final_count,
            bucket_tone_matrix,
            bucket_tone_count,
            DEFAULT_SHARED_IDENTITY_WEIGHT,
        )
        return matrix, {
            "anchor_weight": DEFAULT_ANCHOR_WEIGHT,
            "shared_identity_weight": DEFAULT_SHARED_IDENTITY_WEIGHT,
        }

    matrix = np.zeros((size, size), dtype=float)
    shared_alignment_cache: Optional[Dict[Tuple[str, int, int], Dict[str, Any]]] = (
        {} if phoneme_mode == "shared_request_identity" else None
    )
    anchor_signature_cache: Optional[Dict[Tuple[int, int], np.ndarray]] = (
        {} if phoneme_mode == "anchored_inventory" else None
    )

    prepared_groups = []
    for group in group_models:
        prepared_groups.append(
            {
                "compare_dimension": group["compare_dimension"],
                "group_weight": float(group["group_weight"]),
                "use_phonetic_values": bool(group["use_phonetic_values"]),
                "phonetic_value_weight": float(group["phonetic_value_weight"]),
                "token_catalog": group["token_catalog"],
                "location_states": [group["locations"][location] for location in locations],
            }
        )

    bucket_states_by_dimension: Dict[str, List[Dict[str, Any]]] = {}
    if phoneme_mode == "shared_request_identity":
        bucket_states_by_dimension = {
            dimension: [bucket_models[dimension]["locations"][location] for location in locations]
            for dimension in bucket_models
        }

    inventory_profiles_by_dimension: Dict[str, List[Dict[str, Dict[str, float]]]] = {}
    if phoneme_mode == "anchored_inventory":
        inventory_profiles_by_dimension = {
            dimension: [
                inventory_profiles.get(location, {}).get(dimension, {})
                for location in locations
            ]
            for dimension in sorted({group["compare_dimension"] for group in group_models})
        }

    for row_start in range(0, size, block_size):
        row_end = min(size, row_start + block_size)
        for col_start in range(row_start, size, block_size):
            col_end = min(size, col_start + block_size)
            for i in range(row_start, row_end):
                j_begin = max(i + 1, col_start) if col_start == row_start else col_start
                for j in range(j_begin, col_end):
                    total = 0.0
                    weight_sum = 0.0

                    for group in prepared_groups:
                        state_a = group["location_states"][i]
                        state_b = group["location_states"][j]
                        if (
                            state_a["present_char_count"] == 0
                            and state_b["present_char_count"] == 0
                        ):
                            continue

                        weight = group["group_weight"]
                        weight_sum += weight
                        if (
                            state_a["present_char_count"] == 0
                            or state_b["present_char_count"] == 0
                        ):
                            total += weight * 1.0
                            continue

                        group_alignment = build_alignment_info(
                            state_a["token_ids"],
                            state_b["token_ids"],
                        )
                        d_corr = conditional_entropy_distance_from_counts(
                            group_alignment["count_xy"],
                            group_alignment["count_x"],
                            group_alignment["count_y"],
                            group_alignment["total"],
                        )
                        d_struct = pair_relation_distance_from_counts(
                            group_alignment["count_xy"],
                            group_alignment["count_x"],
                            group_alignment["count_y"],
                            group_alignment["total"],
                        )
                        d_intra = INTRA_CORR_WEIGHT * d_corr + INTRA_STRUCT_WEIGHT * d_struct

                        d_phoneme = d_intra
                        value_map_a_to_b = group_alignment["map_a_to_b"]
                        value_map_b_to_a = group_alignment["map_b_to_a"]

                        if phoneme_mode == "anchored_inventory":
                            dimension = group["compare_dimension"]
                            profile_a = inventory_profiles_by_dimension[dimension][i]
                            profile_b = inventory_profiles_by_dimension[dimension][j]
                            d_anchor = anchor_distance(
                                group_alignment["count_x"],
                                group_alignment["count_y"],
                                group_alignment["token_ids_x"],
                                group_alignment["token_ids_y"],
                                group_alignment["map_a_to_b"],
                                group_alignment["map_b_to_a"],
                                profile_a,
                                profile_b,
                                group["token_catalog"],
                                signature_cache=anchor_signature_cache,
                            )
                            d_phoneme = (
                                (1.0 - DEFAULT_ANCHOR_WEIGHT) * d_intra
                                + DEFAULT_ANCHOR_WEIGHT * d_anchor
                            )
                        elif phoneme_mode == "shared_request_identity":
                            dimension = group["compare_dimension"]
                            cache_key = (dimension, i, j)
                            if cache_key not in shared_alignment_cache:
                                bucket_state_a = bucket_states_by_dimension[dimension][i]
                                bucket_state_b = bucket_states_by_dimension[dimension][j]
                                shared_alignment_cache[cache_key] = build_alignment_info(
                                    bucket_state_a["token_ids"],
                                    bucket_state_b["token_ids"],
                                    include_lookup=True,
                                )
                            shared_alignment = shared_alignment_cache[cache_key]
                            d_shared = conditional_entropy_distance_with_model(
                                state_a["token_ids"],
                                state_b["token_ids"],
                                shared_alignment,
                            )
                            d_phoneme = (
                                (1.0 - DEFAULT_SHARED_IDENTITY_WEIGHT) * d_intra
                                + DEFAULT_SHARED_IDENTITY_WEIGHT * d_shared
                            )
                            value_map_a_to_b = project_model_mapping(
                                group_alignment["token_ids_x"],
                                shared_alignment["index_x"],
                                shared_alignment["map_a_to_b"],
                            )
                            value_map_b_to_a = project_model_mapping(
                                group_alignment["token_ids_y"],
                                shared_alignment["index_y"],
                                shared_alignment["map_b_to_a"],
                            )

                        group_distance = d_phoneme
                        if group["use_phonetic_values"]:
                            phonetic_weight = group["phonetic_value_weight"]
                            d_value = aligned_value_distance(
                                group_alignment["count_x"],
                                group_alignment["count_y"],
                                group_alignment["token_ids_x"],
                                group_alignment["token_ids_y"],
                                value_map_a_to_b,
                                value_map_b_to_a,
                                group["token_catalog"],
                            )
                            group_distance = (
                                (1.0 - phonetic_weight) * d_phoneme
                                + phonetic_weight * d_value
                            )

                        total += weight * group_distance

                    distance = (total / weight_sum) if weight_sum > 0 else 1.0
                    matrix[i, j] = distance
                    matrix[j, i] = distance

    return matrix, {
        "anchor_weight": DEFAULT_ANCHOR_WEIGHT,
        "shared_identity_weight": DEFAULT_SHARED_IDENTITY_WEIGHT,
    }
