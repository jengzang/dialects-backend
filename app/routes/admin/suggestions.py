from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas.user.suggestions import (
    AdminSuggestionUpdate,
    SuggestionItem,
    SuggestionListResponse,
)
from app.service.admin import suggestions as suggestion_admin_service
from app.service.auth.core.dependencies import get_current_admin_user
from app.service.auth.database.models import User
from app.service.user.core.database import get_db as get_db_custom

router = APIRouter()


@router.get("", response_model=SuggestionListResponse)
async def list_suggestions(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db_custom),
    admin_user: User = Depends(get_current_admin_user),
):
    _ = admin_user
    try:
        return suggestion_admin_service.list_suggestions_admin(
            db,
            status=status,
            category=category,
            user_id=user_id,
            q=q,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取建议列表失败: {str(exc)}")


@router.patch("/{suggestion_id}", response_model=SuggestionItem)
async def update_suggestion(
    suggestion_id: int,
    payload: AdminSuggestionUpdate,
    db: Session = Depends(get_db_custom),
    admin_user: User = Depends(get_current_admin_user),
):
    try:
        result = suggestion_admin_service.update_suggestion_admin(
            db,
            suggestion_id,
            payload,
            admin_user,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新建议失败: {str(exc)}")

    if result is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    return result
