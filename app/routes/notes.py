from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.schemas.notes import NotesSearchResponse
from app.service.notes import query_notes
from app.sql.db_selector import get_dialects_db, get_query_db


router = APIRouter()


@router.get("/notes", response_model=NotesSearchResponse)
async def get_notes(
    q: str = Query(..., description="搜索 IPA 或注释"),
    search_fields: list[str] | None = Query(default=None),
    locations: list[str] | None = Query(default=None, description="地点列表"),
    regions: list[str] | None = Query(default=None, description="分区列表"),
    region_mode: str = Query("yindian", description="分区模式: yindian/map"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    notes_db: str = Depends(get_dialects_db),
    query_db: str = Depends(get_query_db),
):
    if region_mode not in {"map", "yindian"}:
        raise HTTPException(status_code=400, detail="region_mode must be map or yindian")

    try:
        return await run_in_threadpool(
            query_notes,
            q=q,
            search_fields=search_fields,
            locations=locations,
            regions=regions,
            region_mode=region_mode,
            page=page,
            page_size=page_size,
            notes_db_path=notes_db,
            query_db_path=query_db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
