import math
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.schemas.toponyms import (
    ToponymDetailsResponse,
    ToponymDivisionsResponse,
    ToponymNameTreeLazyChildrenResponse,
    ToponymNameTreeLazyFallbackResponse,
    ToponymNameTreeLazyNamesResponse,
    ToponymNameTreeResponse,
    ToponymNamesResponse,
    ToponymPointsResponse,
    ToponymSearchResponse,
)
from app.service.toponyms.config import (
    DEFAULT_NAME_LIMIT,
    DEFAULT_POINT_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    MAX_DETAIL_IDS,
    MAX_NAME_LIMIT,
    MAX_POINT_LIMIT,
    MAX_SEARCH_LIMIT,
    NATURAL_VILLAGE_PLACE_TYPE_CODES,
    TOPONYM_NAME_TREE_DEFAULT_PAGE_SIZE,
    TOPONYM_NAME_TREE_MAX_PAGE_SIZE,
)
from app.service.toponyms.repository import (
    list_details_by_ids,
    list_child_divisions,
    list_names_with_division_tree,
    list_points_by_name,
    sample_names,
    search_toponyms,
)

router = APIRouter()


MatchMode = Literal["prefix", "suffix", "exact", "contains"]
AreaScope = Literal["descendants", "exact"]


def _clean_query(query: str | None) -> str:
    cleaned = (query or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="q is required")
    return cleaned


def _clean_place_type_codes(raw_codes: list[str]) -> list[str]:
    codes: list[str] = []
    for raw_value in raw_codes:
        for part in raw_value.split(","):
            cleaned = part.strip()
            if not cleaned or not cleaned.isdigit():
                raise HTTPException(status_code=400, detail=f"place_type_code must be a non-empty numeric string, got: {cleaned!r}")
            if cleaned not in codes:
                codes.append(cleaned)
    if not codes:
        raise HTTPException(status_code=400, detail="place_type_code is required")
    return codes


def _clean_area_code(area_code: str | None) -> str | None:
    if area_code is None or area_code.strip() == "":
        return None
    cleaned = area_code.strip()
    if not cleaned.isdigit():
        raise HTTPException(status_code=400, detail="area_code must be a numeric string")
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


def _clean_parent_path(raw_parent_path: list[str] | None) -> list[str] | None:
    if raw_parent_path is None:
        return None

    parent_path = [part.strip() for part in raw_parent_path if part.strip()]
    if not parent_path:
        return None
    if len(parent_path) > 4:
        raise HTTPException(status_code=400, detail="parent_path cannot contain more than 4 values")
    return parent_path


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
    place_type_code: list[str] = Query(None, description="默认 22200 自然村/农村居民点，可逗号分隔或重复传参"),
) -> ToponymPointsResponse:
    del zoom
    cleaned_query = _clean_query(q)
    cleaned_place_type_codes = _clean_place_type_codes(place_type_code or NATURAL_VILLAGE_PLACE_TYPE_CODES)
    parsed_bbox = _parse_bbox(bbox)

    items, truncated = await run_in_threadpool(
        list_points_by_name,
        query=cleaned_query,
        match_mode=match_mode,
        limit=limit,
        place_type_codes=cleaned_place_type_codes,
        bbox=parsed_bbox,
    )
    return ToponymPointsResponse(items=items, count=len(items), truncated=truncated)


@router.get("/toponyms/search", response_model=ToponymSearchResponse, response_model_exclude_none=True)
async def search_toponym_records(
    q: str | None = Query(None, description="地名查询文本"),
    match_mode: MatchMode = Query("prefix", description="prefix, suffix, exact, contains"),
    bbox: str | None = Query(None, description="可选: minLng,minLat,maxLng,maxLat；仅过滤 single 点位"),
    limit: int = Query(DEFAULT_SEARCH_LIMIT, ge=0, le=MAX_SEARCH_LIMIT, description="0 表示不限制"),
    place_type_code: list[str] = Query(None, description="默认 22200 自然村/农村居民点，可逗号分隔或重复传参"),
    area_code: str | None = Query(None, description="可选行政区划 code"),
    area_scope: AreaScope = Query("descendants", description="descendants 匹配下级，exact 仅精确匹配 area_code"),
    include_area_code: bool = Query(False, description="true 时额外返回 area_code"),
    include_place_type_code: bool = Query(False, description="true 时额外返回 place_type_code"),
) -> ToponymSearchResponse:
    cleaned_query = _clean_query(q)
    cleaned_place_type_codes = _clean_place_type_codes(place_type_code or NATURAL_VILLAGE_PLACE_TYPE_CODES)
    cleaned_area_code = _clean_area_code(area_code)
    parsed_bbox = _parse_bbox(bbox)

    items, truncated = await run_in_threadpool(
        search_toponyms,
        query=cleaned_query,
        match_mode=match_mode,
        limit=limit,
        place_type_codes=cleaned_place_type_codes,
        area_code=cleaned_area_code,
        area_scope=area_scope,
        bbox=parsed_bbox,
        include_area_code=include_area_code,
        include_place_type_code=include_place_type_code,
    )
    return ToponymSearchResponse(items=items, count=len(items), truncated=truncated)


ToponymNamesEndpointResponse = (
    ToponymNamesResponse
    | ToponymNameTreeResponse
    | ToponymNameTreeLazyFallbackResponse
    | ToponymNameTreeLazyChildrenResponse
    | ToponymNameTreeLazyNamesResponse
)


@router.get("/toponyms/names", response_model=ToponymNamesEndpointResponse)
async def get_toponym_names(
    q: str = Query(..., min_length=1),
    match_mode: MatchMode = Query("prefix", description="prefix, suffix, exact, contains"),
    limit: int = Query(DEFAULT_NAME_LIMIT, ge=0, le=MAX_NAME_LIMIT),
    bbox: str | None = Query(None, description="可选: minLng,minLat,maxLng,maxLat"),
    include_division_tree: bool = Query(False, description="true 时返回行政区划层级树"),
    parent_path: list[str] | None = Query(None, description="懒加载树节点路径，可重复传参"),
    page: int = Query(1, ge=1, description="懒加载叶子名称页码"),
    page_size: int = Query(
        TOPONYM_NAME_TREE_DEFAULT_PAGE_SIZE,
        ge=1,
        le=TOPONYM_NAME_TREE_MAX_PAGE_SIZE,
        description="懒加载叶子名称每页数量",
    ),
    place_type_code: list[str] = Query(None, description="默认 22200 自然村/农村居民点，可逗号分隔或重复传参"),
) -> ToponymNamesEndpointResponse:
    cleaned_query = _clean_query(q)
    cleaned_place_type_codes = _clean_place_type_codes(place_type_code or NATURAL_VILLAGE_PLACE_TYPE_CODES)
    parsed_bbox = _parse_bbox(bbox)
    cleaned_parent_path = _clean_parent_path(parent_path)
    if include_division_tree:
        result = await run_in_threadpool(
            list_names_with_division_tree,
            query=cleaned_query,
            match_mode=match_mode,
            limit=limit,
            place_type_codes=cleaned_place_type_codes,
            bbox=parsed_bbox,
            parent_path=cleaned_parent_path,
            page=page,
            page_size=page_size,
        )
        if result["mode"] == "full":
            return ToponymNameTreeResponse(**result)
        if result["mode"] == "lazy_fallback":
            return ToponymNameTreeLazyFallbackResponse(**result)
        if "names" in result:
            return ToponymNameTreeLazyNamesResponse(**result)
        return ToponymNameTreeLazyChildrenResponse(**result)

    names = await run_in_threadpool(
        sample_names,
        query=cleaned_query,
        match_mode=match_mode,
        limit=limit,
        place_type_codes=cleaned_place_type_codes,
        bbox=parsed_bbox,
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
