from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.schemas.toponyms import (
    ToponymDivisionsResponse,
    ToponymNamesResponse,
    ToponymPointsResponse,
)
from app.service.toponyms.config import (
    DEFAULT_NAME_LIMIT,
    MAX_NAME_LIMIT,
)
from app.service.toponyms.repository import (
    list_child_divisions,
    list_all_points,
    sample_names,
)

router = APIRouter()


@router.get("/toponyms/points", response_model=ToponymPointsResponse)
async def get_toponym_points(
    bbox: str | None = Query(None, include_in_schema=False),
    zoom: int | None = Query(None, include_in_schema=False),
    limit: int | None = Query(None, include_in_schema=False),
) -> ToponymPointsResponse:
    if bbox is not None or zoom is not None or limit is not None:
        raise HTTPException(status_code=400, detail="toponyms points is a full export endpoint; query parameters are not supported")

    items = await run_in_threadpool(list_all_points)
    return ToponymPointsResponse(items=items, count=len(items), truncated=False)


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
