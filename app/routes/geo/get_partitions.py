"""Default partition tree API, with complete paths as node identities."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.service.geo.partitions import get_partition_tree
from app.sql.db_selector import get_query_db

router = APIRouter()


@router.get("/partitions")
def api_get_partitions(
    parent: Optional[str] = Query(None),
    region_mode: Literal["map", "yindian"] = Query("yindian"),
    query_db: str = Depends(get_query_db),
):
    """Return visible roots, or the descendants of a complete parent path."""
    try:
        return get_partition_tree(query_db, region_mode, parent)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Partition path not found") from error
