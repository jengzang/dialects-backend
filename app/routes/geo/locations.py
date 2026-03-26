from fastapi import APIRouter, Depends, Query

from app.service.geo.locations import get_location_detail_rows, get_location_partition_rows
from app.sql.db_selector import get_query_db


router = APIRouter()


@router.get("/locations/detail")
async def get_location_detail(
    name: str = Query(..., description="地點簡稱"),
    query_db: str = Depends(get_query_db),
):
    return {"data": get_location_detail_rows(name=name, query_db=query_db)}


@router.get("/locations/partitions")
async def get_location_partitions(
    query_db: str = Depends(get_query_db),
):
    return {"data": get_location_partition_rows(query_db=query_db)}
