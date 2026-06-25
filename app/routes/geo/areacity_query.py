from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.geo_query.loader import get_geo_engine

router = APIRouter()


class GeometryQueryBody(BaseModel):
    geometry: dict[str, Any]


@router.get("/geo/status")
def geo_status(engine=Depends(get_geo_engine)):
    return asdict(engine.get_status())


@router.get("/geo/query/point")
def geo_query_point(
    lng: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    engine=Depends(get_geo_engine),
):
    return asdict(engine.query_point(lng, lat))


@router.get("/geo/query/point-with-tolerance")
def geo_query_point_with_tolerance(
    lng: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    tolerance_metre: int = Query(2500, ge=0),
    engine=Depends(get_geo_engine),
):
    return asdict(engine.query_point_with_tolerance(lng, lat, tolerance_metre))


@router.post("/geo/query/geometry")
def geo_query_geometry(body: GeometryQueryBody, engine=Depends(get_geo_engine)):
    if body.geometry.get("type") not in {"Polygon", "MultiPolygon"}:
        raise HTTPException(status_code=422, detail="Only Polygon and MultiPolygon are supported")
    if "coordinates" not in body.geometry:
        raise HTTPException(status_code=422, detail="GeoJSON geometry must include coordinates")
    return asdict(engine.query_geometry(body.geometry))


@router.get("/geo/boundary/by-id")
def geo_boundary_by_id(feature_id: int = Query(..., ge=1), engine=Depends(get_geo_engine)):
    result = engine.read_boundary_by_id(feature_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    return result


@router.get("/geo/search")
def geo_search(q: str = Query(..., min_length=1), deep: int | None = Query(None, ge=0, le=2), engine=Depends(get_geo_engine)):
    return {"success": True, "items": engine.search(q, deep)}


@router.get("/geo/children")
def geo_children(
    parent_id: int | None = Query(None, ge=0),
    deep: int | None = Query(None, ge=0, le=2),
    engine=Depends(get_geo_engine),
):
    return {"success": True, "items": engine.children(parent_id, deep)}
