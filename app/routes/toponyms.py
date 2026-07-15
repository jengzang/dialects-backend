import math
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.schemas.toponyms import (
    ToponymDivisionsResponse,
    ToponymNamesResponse,
    ToponymPointsResponse,
)
from app.service.toponyms.config import (
    DEFAULT_NAME_LIMIT,
    DEFAULT_POINT_LIMIT,
    MAX_NAME_LIMIT,
    MAX_POINT_LIMIT,
)
from app.service.toponyms.repository import (
    list_child_divisions,
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
) -> ToponymPointsResponse:
    del zoom
    cleaned_query = _clean_query(q)
    parsed_bbox = _parse_bbox(bbox)

    items, truncated = await run_in_threadpool(
        list_points_by_name,
        query=cleaned_query,
        match_mode=match_mode,
        limit=limit,
        bbox=parsed_bbox,
    )
    return ToponymPointsResponse(items=items, count=len(items), truncated=truncated)


@router.get("/toponyms/names/sample", response_model=ToponymNamesResponse)
async def get_toponym_name_samples(
    q: str = Query(..., min_length=1),
    match_mode: MatchMode = Query("prefix", description="prefix, suffix, exact, contains"),
    limit: int = Query(DEFAULT_NAME_LIMIT, ge=0, le=MAX_NAME_LIMIT),
) -> ToponymNamesResponse:
    cleaned_query = _clean_query(q)
    names = await run_in_threadpool(
        sample_names,
        query=cleaned_query,
        match_mode=match_mode,
        limit=limit,
    )
    return ToponymNamesResponse(items=names)


@router.get("/toponyms/divisions", response_model=ToponymDivisionsResponse)
async def get_toponym_divisions(
    parent_code: str = Query("100000", min_length=1),
) -> ToponymDivisionsResponse:
    items = await run_in_threadpool(list_child_divisions, parent_code=parent_code.strip())
    return ToponymDivisionsResponse(items=items)
