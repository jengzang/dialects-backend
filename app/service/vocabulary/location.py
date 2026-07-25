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
    raw_location_json: str = ""


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

    raw_location_json = json.dumps(payload_map, ensure_ascii=False, sort_keys=True)
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
        raw_location_json=raw_location_json,
    )
