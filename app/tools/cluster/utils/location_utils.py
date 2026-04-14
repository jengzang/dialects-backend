"""
地点展示字段与调类轮廓相关工具。

聚类计算本身主要依赖 dialect 行中的音系数据，但前端结果展示仍需要行政区、
经纬度、音典分区、调类信息等字段，因此统一在这里做整形。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import numpy as np

from app.tools.cluster.config import TONE_SLOT_COLUMNS

from .common import safe_text


def parse_coordinates(raw_value: Any) -> Optional[Dict[str, float]]:
    """把数据库中的 `经纬度` 文本解析成经度/纬度对象。"""
    text = safe_text(raw_value)
    if not text or "," not in text:
        return None

    left, right = text.split(",", 1)
    try:
        return {
            "longitude": float(left.strip()),
            "latitude": float(right.strip()),
        }
    except ValueError:
        return None


def normalize_tone_contour(raw_value: Any) -> List[float]:
    """
    把调值字符串压成固定 4 维向量。

    返回格式是：
    - 第 1 维固定为 1，表示该调类存在；
    - 后 3 维分别表示起点 / 中点 / 终点，且归一化到 0~1。
    """
    text = safe_text(raw_value)
    if not text:
        return [0.0, 0.0, 0.0, 0.0]

    contours: List[List[float]] = []
    cleaned = re.sub(r"\[[^\]]+\]", "", text)
    for part in re.split(r"[，,;；/]+", cleaned):
        match = re.search(r"([0-5]+)", part)
        if not match:
            continue
        digits = [int(char) for char in match.group(1)]
        if not digits:
            continue
        if len(digits) == 1:
            contour = [digits[0], digits[0], digits[0]]
        elif len(digits) == 2:
            contour = [digits[0], (digits[0] + digits[1]) / 2.0, digits[1]]
        else:
            middle = digits[len(digits) // 2]
            contour = [digits[0], middle, digits[-1]]
        contours.append(contour)

    if not contours:
        return [0.0, 0.0, 0.0, 0.0]

    averaged = np.mean(np.asarray(contours, dtype=float), axis=0) / 5.0
    return [1.0, float(averaged[0]), float(averaged[1]), float(averaged[2])]


def build_tone_system_vector(location_detail: Optional[Dict[str, Any]]) -> np.ndarray:
    """把一个地点的所有调类槽位拼成统一长度的调系向量。"""
    if not location_detail:
        return np.zeros(len(TONE_SLOT_COLUMNS) * 4, dtype=float)

    tone_classes = location_detail.get("tone_classes") or {}
    values: List[float] = []
    for column in TONE_SLOT_COLUMNS:
        values.extend(normalize_tone_contour(tone_classes.get(column)))
    return np.asarray(values, dtype=float)


def public_location_detail(location_detail: Dict[str, Any]) -> Dict[str, Any]:
    """筛出允许返回给前端的地点详情字段。"""
    return {
        "location": location_detail.get("location"),
        "province": location_detail.get("province"),
        "city": location_detail.get("city"),
        "county": location_detail.get("county"),
        "town": location_detail.get("town"),
        "administrative_village": location_detail.get("administrative_village"),
        "natural_village": location_detail.get("natural_village"),
        "coordinates": location_detail.get("coordinates"),
        "yindian_region": location_detail.get("yindian_region"),
        "map_region": location_detail.get("map_region"),
        "tone_classes": location_detail.get("tone_classes") or {},
    }
