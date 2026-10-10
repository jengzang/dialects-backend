import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class NormalizedLocation:
    location_name: str
    coordinates: str
    province: str = ""
    city: str = ""
    county: str = ""
    town: str = ""
    administrative_village: str = ""
    natural_village: str = ""
    yindian_region: str = ""
    atlas_region: str = ""
    vocabulary_source: str = ""
    description: str = ""
    other: str = ""
    t1: str = ""
    t2: str = ""
    t3: str = ""
    t4: str = ""
    t5: str = ""
    t6: str = ""
    t7: str = ""
    t8: str = ""
    t9: str = ""
    t10: str = ""


_LOCATION_ALIASES = {
    "location_name": ("location_name", "簡稱", "简称", "地名", "name", "location"),
    "coordinates": ("coordinates", "經緯度", "经纬度", "经纬度", "lnglat", "latlng"),
    "province": ("province", "省"),
    "city": ("city", "市"),
    "county": ("county", "縣", "县", "區縣", "区县"),
    "town": ("town", "鎮", "镇", "鄉鎮", "乡镇"),
    "administrative_village": (
        "administrative_village",
        "行政村",
    ),
    "natural_village": ("natural_village", "自然村"),
    "yindian_region": ("yindian_region", "音典分區", "音典分区"),
    "atlas_region": (
        "atlas_region",
        "地圖集二分區",
        "地图集二分区",
        "地圖集分區",
        "地图集分区",
        "分區",
        "分区",
    ),
    "vocabulary_source": ("vocabulary_source", "source", "词表来源", "詞表來源"),
    "description": ("description", "说明", "說明"),
    "other": ("other", "其他"),
    "t1": ("t1", "T1"),
    "t2": ("t2", "T2"),
    "t3": ("t3", "T3"),
    "t4": ("t4", "T4"),
    "t5": ("t5", "T5"),
    "t6": ("t6", "T6"),
    "t7": ("t7", "T7"),
    "t8": ("t8", "T8"),
    "t9": ("t9", "T9"),
    "t10": ("t10", "T10"),
}


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _get_alias(payload: Mapping[str, Any], field: str) -> str:
    for key in _LOCATION_ALIASES[field]:
        value = _clean_value(payload.get(key))
        if value:
            return value
    return ""


def normalize_location_payload(payload: Mapping[str, Any] | str) -> NormalizedLocation:
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("location must be a valid JSON object") from exc
        if not isinstance(parsed, dict):
            raise ValueError("location must be a valid JSON object")
        payload_map: Mapping[str, Any] = parsed
    else:
        payload_map = payload

    values = {
        field: _get_alias(payload_map, field)
        for field in _LOCATION_ALIASES
    }

    if not values["location_name"]:
        raise ValueError("location_name is required")
    if not values["coordinates"]:
        raise ValueError("coordinates is required")

    return NormalizedLocation(
        location_name=values["location_name"],
        coordinates=values["coordinates"],
        province=values["province"],
        city=values["city"],
        county=values["county"],
        town=values["town"],
        administrative_village=values["administrative_village"],
        natural_village=values["natural_village"],
        yindian_region=values["yindian_region"],
        atlas_region=values["atlas_region"],
        vocabulary_source=values["vocabulary_source"],
        description=values["description"],
        other=values["other"],
        t1=values["t1"],
        t2=values["t2"],
        t3=values["t3"],
        t4=values["t4"],
        t5=values["t5"],
        t6=values["t6"],
        t7=values["t7"],
        t8=values["t8"],
        t9=values["t9"],
        t10=values["t10"],
    )
