from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.schemas.vocabulary import (
    VocabularyItemsResponse,
    VocabularyPermissionResponse,
    VocabularyPermissionUpdateRequest,
    VocabularyUploadResponse,
)
from app.service.auth.core.dependencies import get_current_admin_user, get_current_user
from app.service.auth.database.models import User
from app.service.vocabulary.database import get_db as get_vocabulary_db
from app.service.vocabulary.logging import record_vocabulary_log
from app.service.vocabulary.models import VocabularyPermission
from app.service.vocabulary.query import query_vocabulary_items
from app.service.vocabulary.service import import_vocabulary_upload


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


@router.put("/admin/permissions/{user_id}", response_model=VocabularyPermissionResponse)
def set_vocabulary_permission(
    user_id: int,
    params: VocabularyPermissionUpdateRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission = db.query(VocabularyPermission).filter(
        VocabularyPermission.user_id == user_id
    ).first()
    if permission is None:
        permission = VocabularyPermission(
            user_id=user_id,
            permission_level=params.permission_level,
        )
        db.add(permission)
    else:
        permission.permission_level = params.permission_level

    record_vocabulary_log(
        session=db,
        user_id=current_admin.id,
        permission_level="manage",
        source="admin",
        action="set_permission",
        table_name="vocabulary_permissions",
        target_scope=f"target_user_id = {user_id}",
        affected_rows=1,
        payload={
            "target_user_id": user_id,
            "permission_level": params.permission_level,
        },
    )
    db.commit()
    db.refresh(permission)
    return VocabularyPermissionResponse(
        user_id=permission.user_id,
        permission_level=permission.permission_level,
    )
