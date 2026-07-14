import math

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
    MAX_BBOX_AREA,
    MAX_NAME_LIMIT,
    MAX_POINT_LIMIT,
)
from app.service.toponyms.repository import (
    list_child_divisions,
    list_points_in_bbox,
    sample_names,
)

router = APIRouter()


def _parse_bbox(raw_bbox: str) -> tuple[float, float, float, float]:
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
    if (max_lng - min_lng) * (max_lat - min_lat) > MAX_BBOX_AREA:
        raise HTTPException(status_code=400, detail="bbox is too large; zoom in or split the request")

    return min_lng, min_lat, max_lng, max_lat


@router.get("/toponyms/points", response_model=ToponymPointsResponse)
async def get_toponym_points(
    bbox: str = Query(..., description="minLng,minLat,maxLng,maxLat"),
    zoom: int | None = Query(None, ge=0, le=24),
    limit: int = Query(DEFAULT_POINT_LIMIT, ge=1, le=MAX_POINT_LIMIT),
) -> ToponymPointsResponse:
    del zoom
    min_lng, min_lat, max_lng, max_lat = _parse_bbox(bbox)
    items, truncated = await run_in_threadpool(
        list_points_in_bbox,
        min_lng=min_lng,
        min_lat=min_lat,
        max_lng=max_lng,
        max_lat=max_lat,
        limit=limit,
    )
    return ToponymPointsResponse(items=items, count=len(items), truncated=truncated)


@router.get("/toponyms/names/sample", response_model=ToponymNamesResponse)
async def get_toponym_name_samples(
    q: str = Query(..., min_length=1),
    limit: int = Query(DEFAULT_NAME_LIMIT, ge=1, le=MAX_NAME_LIMIT),
) -> ToponymNamesResponse:
    names = await run_in_threadpool(sample_names, query=q.strip(), limit=limit)
    return ToponymNamesResponse(items=names)


@router.get("/toponyms/divisions", response_model=ToponymDivisionsResponse)
async def get_toponym_divisions(
    parent_code: str = Query("100000", min_length=1),
) -> ToponymDivisionsResponse:
    items = await run_in_threadpool(list_child_divisions, parent_code=parent_code.strip())
    return ToponymDivisionsResponse(items=items)
