from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.schemas.vocabulary import VocabularyItemsResponse, VocabularyUploadResponse
from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.models import User
from app.service.vocabulary.database import get_db as get_vocabulary_db
from app.service.vocabulary.service import import_vocabulary_upload, query_vocabulary_items


router = APIRouter()


@router.get("/items", response_model=VocabularyItemsResponse)
def get_vocabulary_items(
    q: Optional[str] = Query(default=None),
    search_fields: Optional[list[str]] = Query(default=None),
    locations: Optional[list[str]] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_vocabulary_db),
):
    try:
        return query_vocabulary_items(
            session=db,
            q=q,
            search_fields=search_fields,
            locations=locations,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vocabulary query failed: {exc}") from exc


@router.post("/upload", response_model=VocabularyUploadResponse)
async def upload_vocabulary(
    file: UploadFile = File(...),
    location: str = Form(...),
    parser_mode: str = Form("auto"),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    content = await file.read()
    try:
        return import_vocabulary_upload(
            session=db,
            user=current_user,
            filename=file.filename or "upload",
            content=content,
            location_payload=location,
            parser_mode=parser_mode,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vocabulary upload failed: {exc}")
