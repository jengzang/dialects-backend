"""
cluster 音系距离建模层。

这是整个 cluster 功能里最核心、也最容易看迷糊的一层。
它负责三件事：
1. 把地点-汉字-读音集合编码成 token id 矩阵；
2. 按三种 phoneme_mode 计算地点两两之间的音系距离；
3. 在满足条件时切到 numba 快路径，加速大规模请求。

这里说的“距离矩阵”始终指语言样本之间的音系距离，不是地理空间距离。
"""

from __future__ import annotations

import math
import os
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
try:
    from numba import njit, prange, threading_layer
    from numba.typed import List as NumbaList
    NUMBA_AVAILABLE = True
except Exception:  # pragma: no cover - optional accelerator
    # numba 不可用时，保留同名装饰器桩函数，让 Python 回退路径仍能工作。
    def njit(*args, **kwargs):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator
    prange = range
    def threading_layer():  # type: ignore[misc]
        raise ValueError("Threading layer is not initialized.")
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


_NUMBA_PARALLEL_CALL_LOCK = threading.RLock()
_NUMBA_THREADSAFE_BACKEND_AVAILABLE: Optional[bool] = None


def _probe_numba_threadsafe_backend_available() -> bool:
    """
    判断当前运行环境里是否存在线程安全的 numba parallel 后端。

    现象上，当前环境若只有 workqueue，可单线程跑通，但两个 Python 线程同时调用
    `@njit(parallel=True)` 会直接被 numba 以 `SIGABRT` 终止。
    """
    global _NUMBA_THREADSAFE_BACKEND_AVAILABLE
    if _NUMBA_THREADSAFE_BACKEND_AVAILABLE is not None:
        return _NUMBA_THREADSAFE_BACKEND_AVAILABLE

    available = False
    for module_name in ("numba.np.ufunc.tbbpool", "numba.np.ufunc.omppool"):
        try:
            __import__(module_name)
            available = True
            break
        except Exception:
            continue

    _NUMBA_THREADSAFE_BACKEND_AVAILABLE = available
    return available


def _numba_parallel_calls_require_serialization() -> bool:
    """
    `workqueue` 不是线程安全后端。

    因此在只剩 workqueue 的环境里，cluster 虽然仍可使用 numba 快路径，
    但必须把 parallel kernel 的入口串行化，否则本地多请求/多线程就会直接崩进程。
    """
    if not NUMBA_AVAILABLE:
        return False

    try:
        active_layer = str(threading_layer() or "").strip().lower()
    except Exception:
        active_layer = ""

    if active_layer:
        return active_layer == "workqueue"

    configured_layer = str(os.getenv("NUMBA_THREADING_LAYER") or "").strip().lower()
    if configured_layer in {"safe", "threadsafe", "tbb", "omp"}:
        return False
    if configured_layer == "workqueue":
        return True

    return not _probe_numba_threadsafe_backend_available()


def _run_numba_parallel_kernel(func, *args):
    if _numba_parallel_calls_require_serialization():
        with _NUMBA_PARALLEL_CALL_LOCK:
            return func(*args)
    return func(*args)


@njit(cache=True, fastmath=True)
def _compute_intra_group_distance_numba(
    token_ids_a: np.ndarray,
    token_ids_b: np.ndarray,
    token_count: int,
    map_x: np.ndarray,
    map_y: np.ndarray,
    inverse_x: np.ndarray,
    inverse_y: np.ndarray,
    count_x: np.ndarray,
    count_y: np.ndarray,
    count_xy: np.ndarray,
    max_count_size: int,
    use_phonetic_values: bool,
    value_weight: float,
    value_matrix: np.ndarray,
) -> float:
    """
    numba 版组内距离计算（已优化：复用预分配的内存池消除高频 malloc 热点，支持值比对待）。
    """
    shared_total = 0
    for index in range(token_ids_a.shape[0]):
        if token_ids_a[index] >= 0 and token_ids_b[index] >= 0:
            shared_total += 1
    if shared_total <= 0:
        return INTRA_CORR_WEIGHT

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

    for index in range(shared_total):
        slot_x = inverse_x[index]
        slot_y = inverse_y[index]
        count_x[slot_x] += 1
        count_y[slot_y] += 1
        count_xy[slot_x * max_count_size + slot_y] += 1

    h_y_given_x = 0.0
    h_x_given_y = 0.0
    same_both = 0.0
    for slot_x in range(size_x):
        for slot_y in range(size_y):
            freq = count_xy[slot_x * max_count_size + slot_y]
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

    if use_phonetic_values and value_weight > 0.0:
        # 重建映射
        slot_to_token_x = np.full(size_x, -1, dtype=np.int32)
        slot_to_token_y = np.full(size_y, -1, dtype=np.int32)
        for index in range(token_ids_a.shape[0]):
            tok_a = token_ids_a[index]
            tok_b = token_ids_b[index]
            if tok_a >= 0 and tok_b >= 0:
                slot_to_token_x[map_x[tok_a]] = tok_a
                slot_to_token_y[map_y[tok_b]] = tok_b
        
        dist_a = 0.0
        for slot_x in range(size_x):
            best_y = -1
            best_freq = -1
            for slot_y in range(size_y):
                freq = count_xy[slot_x * max_count_size + slot_y]
                if freq > best_freq:
                    best_freq = freq
                    best_y = slot_y
            if best_y >= 0:
                tok_a = slot_to_token_x[slot_x]
                tok_b = slot_to_token_y[best_y]
                dist_a += (count_x[slot_x] / float(shared_total)) * value_matrix[tok_a, tok_b]
            else:
                dist_a += count_x[slot_x] / float(shared_total)
        
        dist_b = 0.0
        for slot_y in range(size_y):
            best_x = -1
            best_freq = -1
            for slot_x in range(size_x):
                freq = count_xy[slot_x * max_count_size + slot_y]
                if freq > best_freq:
                    best_freq = freq
                    best_x = slot_x
            if best_x >= 0:
                tok_a = slot_to_token_x[best_x]
                tok_b = slot_to_token_y[slot_y]
                dist_b += (count_y[slot_y] / float(shared_total)) * value_matrix[tok_a, tok_b]
            else:
                dist_b += count_y[slot_y] / float(shared_total)
                
        d_val = 0.5 * (dist_a + dist_b)
        d_intra = (1.0 - value_weight) * d_intra + value_weight * d_val

    # 清除内存涂写
    for index in range(token_ids_a.shape[0]):
        ta = token_ids_a[index]
        tb = token_ids_b[index]
        if ta >= 0: map_x[ta] = -1
        if tb >= 0: map_y[tb] = -1
    for index in range(shared_total):
        sx = inverse_x[index]
        sy = inverse_y[index]
        count_x[sx] = 0
        count_y[sy] = 0
        count_xy[sx * max_count_size + sy] = 0

    return d_intra


@njit(cache=True, fastmath=True)
def _build_alignment_model_numba(
    token_ids_a: np.ndarray,
    token_ids_b: np.ndarray,
    token_count: int,
):
    """
    numba 版对齐模型构建。

    它会从两个地点共享覆盖的 token 中抽取出：
    - 一维边际计数 `count_x` / `count_y`
    - 二维联合计数 `count_xy`
    - 原 token id 到局部槽位的 lookup

    这个结构既可用于 anchored，也可用于 shared identity。
    """
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


@njit(cache=True, fastmath=True)
def _conditional_entropy_distance_with_model_numba(
    token_ids_a: np.ndarray,
    token_ids_b: np.ndarray,
    model_count_xy: np.ndarray,
    model_count_x: np.ndarray,
    model_count_y: np.ndarray,
    model_lookup_x: np.ndarray,
    model_lookup_y: np.ndarray,
) -> float:
    """
    基于“外部提供的对齐模型”计算条件熵距离。

    shared_request_identity 的关键就在这里：
    当前 group 的小字集不自己建模型，而是借用同维度 bucket 的共享模型来衡量
    “这个 group 在整个请求上下文里是否仍保持同样的对应身份”。
    """
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


@njit(cache=True, fastmath=True)
def _compute_group_distance_anchored_numba(
    token_ids_a: np.ndarray,
    token_ids_b: np.ndarray,
    token_count: int,
    signatures_a: np.ndarray,
    signatures_b: np.ndarray,
    anchor_weight: float,
) -> float:
    """
    numba 版 anchored_inventory 距离。

    它先算普通组内距离 `d_intra`，再根据地点内部库存画像求 `d_anchor`，
    最终返回：
    `(1 - anchor_weight) * d_intra + anchor_weight * d_anchor`
    """
    count_xy, count_x, count_y, lookup_x, lookup_y = _build_alignment_model_numba(
        token_ids_a,
        token_ids_b,
        token_count,
    )
    shared_total = int(np.sum(count_x))
    if shared_total <= 0:
        return ((1.0 - anchor_weight) * INTRA_CORR_WEIGHT) + anchor_weight

    # lookup 只知道“token -> 槽位”，这里再反推出“槽位 -> token”，便于查锚点签名。
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

    # 对每个 token 找最稳的映射对象，再比较两边库存画像里的 share / rank 差异。
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


@njit(cache=True, parallel=True, fastmath=True)
def _build_total_distance_matrix_intra_group_numba(
    token_matrices,
    present_count_matrices,
    token_counts: np.ndarray,
    group_weights: np.ndarray,
    use_phonetic_values_arr: np.ndarray,
    value_weights_arr: np.ndarray,
    value_matrices,
) -> np.ndarray:
    """numba 版 `intra_group` 全矩阵构建。"""
    group_count = len(token_matrices)
    size = present_count_matrices[0].shape[0]
    
    max_token_count = 0
    max_char_count = 0
    for group_index in range(group_count):
        if token_counts[group_index] > max_token_count:
            max_token_count = token_counts[group_index]
        if token_matrices[group_index].shape[1] > max_char_count:
            max_char_count = token_matrices[group_index].shape[1]
    
    max_count_size = max_token_count
    if max_char_count < max_token_count:
        max_count_size = max_char_count

    matrix = np.zeros((size, size), dtype=np.float64)
    for i in prange(size):
        # 并行域空间内安全分配单份缓存区
        map_x_buf = np.full(max_token_count, -1, dtype=np.int32)
        map_y_buf = np.full(max_token_count, -1, dtype=np.int32)
        inv_x_buf = np.empty(max_char_count, dtype=np.int32)
        inv_y_buf = np.empty(max_char_count, dtype=np.int32)
        cx_buf = np.zeros(max_count_size, dtype=np.int32)
        cy_buf = np.zeros(max_count_size, dtype=np.int32)
        cxy_buf = np.zeros(max_count_size * max_count_size, dtype=np.int32)
        
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
                    map_x_buf, map_y_buf, inv_x_buf, inv_y_buf, cx_buf, cy_buf, cxy_buf, max_count_size,
                    bool(use_phonetic_values_arr[group_index]),
                    float(value_weights_arr[group_index]),
                    value_matrices[group_index]
                )

            distance = total / weight_sum if weight_sum > 0.0 else 1.0
            matrix[i, j] = distance
            matrix[j, i] = distance
    return matrix


@njit(cache=True, parallel=True, fastmath=True)
def _build_total_distance_matrix_anchored_numba(
    token_matrices,
    present_count_matrices,
    token_counts: np.ndarray,
    group_weights: np.ndarray,
    anchor_signatures,
    anchor_weight: float,
) -> np.ndarray:
    """numba 版 `anchored_inventory` 全矩阵构建。"""
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


@njit(cache=True, parallel=True, fastmath=True)
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
    """
    numba 版 `shared_request_identity` 全矩阵构建。

    和旧逻辑一致，这里按维度分别建共享 bucket：
    - 声母 group 只和声母 bucket 对齐；
    - 韵母 group 只和韵母 bucket 对齐；
    - 声调 group 只和声调 bucket 对齐。
    """
    group_count = len(token_matrices)
    size = present_count_matrices[0].shape[0]
    max_token_count = 0
    max_char_count = 0
    for group_index in range(group_count):
        if token_counts[group_index] > max_token_count:
            max_token_count = token_counts[group_index]
        if token_matrices[group_index].shape[1] > max_char_count:
            max_char_count = token_matrices[group_index].shape[1]
    max_count_size = max_token_count
    if max_char_count < max_token_count:
        max_count_size = max_char_count

    matrix = np.zeros((size, size), dtype=np.float64)
    for i in prange(size):
        # 复用和 intra_group 快路径相同的工作缓冲区，避免 shared 模式落回旧签名。
        map_x_buf = np.full(max_token_count, -1, dtype=np.int32)
        map_y_buf = np.full(max_token_count, -1, dtype=np.int32)
        inv_x_buf = np.empty(max_char_count, dtype=np.int32)
        inv_y_buf = np.empty(max_char_count, dtype=np.int32)
        cx_buf = np.zeros(max_count_size, dtype=np.int32)
        cy_buf = np.zeros(max_count_size, dtype=np.int32)
        cxy_buf = np.zeros(max_count_size * max_count_size, dtype=np.int32)
        dummy_value_matrix = np.zeros((1, 1), dtype=np.float64)

        for j in range(i + 1, size):
            # 对当前地点对 (i, j) 来说，同一维度的共享模型只需要构建一次。
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
                    map_x_buf,
                    map_y_buf,
                    inv_x_buf,
                    inv_y_buf,
                    cx_buf,
                    cy_buf,
                    cxy_buf,
                    max_count_size,
                    False,
                    0.0,
                    dummy_value_matrix,
                )
                # 默认先落在 final；再按 group 的维度切换到对应 bucket。
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
    """
    为每个维度建立 token catalog。

    这里的 token 不是单个读音值，而是“某个字在该地点该维度上的读音集合”，
    例如一个字有多个韵母读法时，会先规范化为稳定排序后的复合 token。
    """
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
    """
    把单个 group 编码成可参与距离计算的结构。

    核心产物是：
    - `token_matrix`：地点 x 汉字 的 token id 矩阵；
    - `present_char_counts`：每个地点在该组实际覆盖了多少字；
    - `locations[*].token_ids`：便于 Python 回退路径直接读取。
    """
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
            # 每个单元格存的是“规范化后的读音集合 token id”，缺失则保留为 -1。
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
    """
    为一对地点构建对齐统计信息。

    它是 Python 回退路径里最基础的中间结构，包含：
    - `count_xy`：联合计数；
    - `count_x / count_y`：边际计数；
    - `map_a_to_b / map_b_to_a`：按最大频次得到的粗映射；
    - 可选的 token -> 槽位索引，用于 shared identity 投影。
    """
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
    """根据联合计数与边际计数计算条件熵距离。"""
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
    """根据“同音/异音成对关系”计算结构差异距离。"""
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
    """
    使用外部共享模型计算条件熵距离。

    和 `conditional_entropy_distance_from_counts()` 不同，这里并不从当前 group 自己建模，
    而是把当前 token 投影到“同维度共享 bucket”建出的模型上去评价稳定性。
    """
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
    """
    比较两个 token 的实际取值集合差异。

    当 `use_phonetic_values=true` 时，会在音类对应距离之外，再混入这一层集合差异。
    """
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
    """
    根据已经对齐好的 token 映射，计算值集合层面的平均距离。

    这一步不是默认主线，只有显式开启 `use_phonetic_values` 时才参与总距离。
    """
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
    """
    为一个 token 在某地点的库存画像中生成 2 维锚点签名。

    目前这 2 维分别是：
    - 平均 share：这个 token 在该地点库存中有多常见；
    - 平均 rank_pct：这个 token 在该地点库存排序里有多核心。
    """
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
    """
    把当前 group 的 token id 映射投影到共享模型的 token 空间中。

    shared_request_identity 开启 `use_phonetic_values` 时，需要先做这一步，
    才能按共享模型给出的映射关系比较值集合差异。
    """
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
    """
    计算 anchored_inventory 里的锚点距离部分。

    直观上，它回答的是：
    “A 的某个 token 虽然对应到 B 的某个 token，但它们在各自系统内部的
    频率地位和排序地位是否相近？”
    """
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
        """按 token 频次加权，累计一个方向上的锚点差异。"""
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
    """
    为 shared_request_identity 构建“按维度聚合”的 bucket 模型。

    它不是把所有 group 混成一个大组，而是：
    - 声母 group 共享一个 initial bucket；
    - 韵母 group 共享一个 final bucket；
    - 声调 group 共享一个 tone bucket。
    """
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
    """把 anchored_inventory 所需的锚点签名预先展开成矩阵，供 numba 快路径直接读取。"""
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
    """把三种维度 bucket 拆成 numba 快路径易消费的矩阵输入。"""
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
    """
    构建整个请求的地点两两音系距离矩阵。

    这是 cluster 的主热点函数。输入是所有 group 的编码结果，输出是：
    - `matrix[i, j]`：地点 i 和 j 的音系距离；
    - `phoneme_mode_params`：本次模式下使用到的权重参数。

    实现上分两条路：
    - 条件满足时走 numba 快路径；
    - 否则回退到 Python/NumPy 路径。
    """
    size = len(locations)
    if (
        NUMBA_AVAILABLE
        and not force_python
        and phoneme_mode == "intra_group"
    ):
        # 纯 intra_group、且不混入值集合距离时，直接走最快的 numba 路径。
        token_matrices = NumbaList()
        present_count_matrices = NumbaList()
        token_counts = np.empty(len(group_models), dtype=np.int32)
        group_weights = np.empty(len(group_models), dtype=np.float64)
        use_phonetic_values_arr = np.zeros(len(group_models), dtype=np.uint8)
        value_weights_arr = np.zeros(len(group_models), dtype=np.float64)
        value_matrices = NumbaList()
        
        for group_index, group in enumerate(group_models):
            token_matrices.append(group["token_matrix"])
            present_count_matrices.append(group["present_char_counts"])
            token_counts[group_index] = len(group["token_catalog"]["tokens"])
            group_weights[group_index] = float(group["group_weight"])
            
            use_val = bool(group.get("use_phonetic_values", False))
            use_phonetic_values_arr[group_index] = 1 if use_val else 0
            value_weights_arr[group_index] = float(group.get("phonetic_value_weight", 0.0))
            
            # Precompute token_value matrix
            if use_val:
                tcat = group["token_catalog"]
                sz = len(tcat["tokens"])
                vmat = np.zeros((sz, sz), dtype=np.float64)
                for _i in range(sz):
                    for _j in range(_i, sz):
                        vdist = token_value_distance_by_id(_i, _j, tcat)
                        vmat[_i, _j] = vdist
                        vmat[_j, _i] = vdist
                value_matrices.append(vmat)
            else:
                value_matrices.append(np.zeros((1, 1), dtype=np.float64))
                
        matrix = _run_numba_parallel_kernel(
            _build_total_distance_matrix_intra_group_numba,
            token_matrices,
            present_count_matrices,
            token_counts,
            group_weights,
            use_phonetic_values_arr,
            value_weights_arr,
            value_matrices,
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
        # anchored 模式要先把各地点各 token 的锚点签名展开成矩阵。
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
        matrix = _run_numba_parallel_kernel(
            _build_total_distance_matrix_anchored_numba,
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
        # shared_request_identity 的快路径按维度分别使用 shared bucket，
        # 与当前 Python 逻辑保持一致，不再把所有维度混成一个总 bucket。
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
        matrix = _run_numba_parallel_kernel(
            _build_total_distance_matrix_shared_multi_dim_numba,
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

    # 以下是 Python 回退路径：逻辑更直观，也方便做等价性对照和调试。
    matrix = np.zeros((size, size), dtype=float)
    shared_alignment_cache: Optional[Dict[Tuple[str, int, int], Dict[str, Any]]] = (
        {} if phoneme_mode == "shared_request_identity" else None
    )
    anchor_signature_cache: Optional[Dict[Tuple[int, int], np.ndarray]] = (
        {} if phoneme_mode == "anchored_inventory" else None
    )

    # 先把字典结构压成更易遍历的列表结构，减少深层字典索引开销。
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

    # 按 block 扫描矩阵，避免超大请求时 Python 双重循环完全失控。
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

                        # 先算该组内自己的对齐统计，这是三种模式共同的基础。
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
                            # anchored：把“系统内库存位置”也混入距离。
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
                            # shared identity：借助同维度共享 bucket 的对齐模型，
                            # 判断当前 group 的对应关系在更大请求上下文里是否仍稳定。
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
                            # 若显式要求混入值集合差异，再按 phonetic_value_weight 二次融合。
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
