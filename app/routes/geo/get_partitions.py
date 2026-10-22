"""Default partition tree API, with complete paths as node identities."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.common.partition_policy import valid_partition_path
from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.models import User
from app.service.user.core.database import get_db

from app.service.geo.partitions import get_partition_tree, resolve_partition_items
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


class PartitionResolveItem(BaseModel):
    text: str = Field(min_length=1)
    kind: Literal["name", "path"]

    @field_validator("text")
    @classmethod
    def validate_text(cls, text):
        if not valid_partition_path(text):
            raise ValueError("Invalid partition name or path")
        return text


class PartitionResolveRequest(BaseModel):
    region_mode: Literal["map", "yindian"]
    scope: Literal["default", "default_and_user"] = "default"
    items: list[PartitionResolveItem]


@router.post("/partitions/resolve")
def api_resolve_partitions(
    payload: PartitionResolveRequest,
    query_db: str = Depends(get_query_db),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    return resolve_partition_items(query_db, payload.region_mode, payload.items, payload.scope, db, user)
