import math
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.schemas.toponyms import (
    ToponymDetailsResponse,
    ToponymDivisionsResponse,
    ToponymNameTreeResponse,
    ToponymNamesResponse,
    ToponymPointsResponse,
)
from app.service.toponyms.config import (
    DEFAULT_NAME_LIMIT,
    DEFAULT_POINT_LIMIT,
    MAX_DETAIL_IDS,
    MAX_NAME_LIMIT,
    MAX_POINT_LIMIT,
    NATURAL_VILLAGE_PLACE_TYPE_CODE,
)
from app.service.toponyms.repository import (
    list_details_by_ids,
    list_child_divisions,
    list_names_with_division_tree,
    list_points_by_name,
    sample_names,
)

router = APIRouter()


MatchMode = Literal["prefix", "suffix", "exact", "contains"]


def _clean_query(query: str | None) -> str:
    cleaned = (query or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="q is required")
    return cleaned


def _clean_place_type_code(place_type_code: str) -> str:
    cleaned = place_type_code.strip()
    if not cleaned or not cleaned.isdigit():
        raise HTTPException(status_code=400, detail="place_type_code must be a non-empty numeric string")
    return cleaned


def _clean_ids(raw_ids: list[str]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_ids:
        for part in raw_value.split(","):
            cleaned = part.strip()
            if not cleaned or cleaned in seen:
                continue
            ids.append(cleaned)
            seen.add(cleaned)

    if not ids:
        raise HTTPException(status_code=400, detail="ids is required")
    if len(ids) > MAX_DETAIL_IDS:
        raise HTTPException(status_code=400, detail=f"ids cannot contain more than {MAX_DETAIL_IDS} values")
    return ids


def _parse_bbox(raw_bbox: str | None) -> tuple[float, float, float, float] | None:
    if raw_bbox is None or raw_bbox.strip() == "":
        return None

    parts = raw_bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="bbox must contain four comma-separated numbers")

    try:
        min_lng, min_lat, max_lng, max_lat = [float(part.strip()) for part in parts]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="bbox values must be numbers") from exc

    values = (min_lng, min_lat, max_lng, max_lat)
    if not all(math.isfinite(value) for value in values):
        raise HTTPException(status_code=400, detail="bbox values must be finite")
    if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180):
        raise HTTPException(status_code=400, detail="bbox longitude must be within -180..180")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise HTTPException(status_code=400, detail="bbox latitude must be within -90..90")
    if min_lng >= max_lng or min_lat >= max_lat:
        raise HTTPException(status_code=400, detail="bbox min values must be smaller than max values")

    return min_lng, min_lat, max_lng, max_lat


@router.get("/toponyms/points", response_model=ToponymPointsResponse)
async def get_toponym_points(
    q: str | None = Query(None, description="地名查询文本"),
    match_mode: MatchMode = Query("prefix", description="prefix, suffix, exact, contains"),
    bbox: str | None = Query(None, description="可选: minLng,minLat,maxLng,maxLat"),
    zoom: int | None = Query(None, ge=0, le=24, description="可选: 前端地图缩放级别，后端仅校验"),
    limit: int = Query(DEFAULT_POINT_LIMIT, ge=0, le=MAX_POINT_LIMIT, description="0 表示不限制"),
    place_type_code: str = Query(NATURAL_VILLAGE_PLACE_TYPE_CODE, min_length=1, description="默认 22200 自然村/农村居民点"),
) -> ToponymPointsResponse:
    del zoom
    cleaned_query = _clean_query(q)
    cleaned_place_type_code = _clean_place_type_code(place_type_code)
    parsed_bbox = _parse_bbox(bbox)

    items, truncated = await run_in_threadpool(
        list_points_by_name,
        query=cleaned_query,
        match_mode=match_mode,
        limit=limit,
        place_type_code=cleaned_place_type_code,
        bbox=parsed_bbox,
    )
    return ToponymPointsResponse(items=items, count=len(items), truncated=truncated)


@router.get("/toponyms/names", response_model=ToponymNamesResponse | ToponymNameTreeResponse)
async def get_toponym_names(
    q: str = Query(..., min_length=1),
    match_mode: MatchMode = Query("prefix", description="prefix, suffix, exact, contains"),
    limit: int = Query(DEFAULT_NAME_LIMIT, ge=0, le=MAX_NAME_LIMIT),
    include_division_tree: bool = Query(False, description="true 时返回行政区划层级树"),
    place_type_code: str = Query(NATURAL_VILLAGE_PLACE_TYPE_CODE, min_length=1, description="默认 22200 自然村/农村居民点"),
) -> ToponymNamesResponse | ToponymNameTreeResponse:
    cleaned_query = _clean_query(q)
    cleaned_place_type_code = _clean_place_type_code(place_type_code)
    if include_division_tree:
        items = await run_in_threadpool(
            list_names_with_division_tree,
            query=cleaned_query,
            match_mode=match_mode,
            limit=limit,
            place_type_code=cleaned_place_type_code,
        )
        return ToponymNameTreeResponse(items=items)

    names = await run_in_threadpool(
        sample_names,
        query=cleaned_query,
        match_mode=match_mode,
        limit=limit,
        place_type_code=cleaned_place_type_code,
    )
    return ToponymNamesResponse(items=names)


@router.get("/toponyms/details", response_model=ToponymDetailsResponse)
async def get_toponym_details(
    ids: list[str] = Query(..., min_length=1, description="逗号分隔或重复传参，最多 10 个 ID"),
) -> ToponymDetailsResponse:
    cleaned_ids = _clean_ids(ids)
    items = await run_in_threadpool(list_details_by_ids, ids=cleaned_ids)
    return ToponymDetailsResponse(items=items, count=len(items))


@router.get("/toponyms/divisions", response_model=ToponymDivisionsResponse)
async def get_toponym_divisions(
    parent_code: str = Query("100000", min_length=1),
) -> ToponymDivisionsResponse:
    items = await run_in_threadpool(list_child_divisions, parent_code=parent_code.strip())
    return ToponymDivisionsResponse(items=items)
