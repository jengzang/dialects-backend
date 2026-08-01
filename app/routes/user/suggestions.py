from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.schemas.user.suggestions import (
    SuggestionCreate,
    SuggestionCreateResponse,
    SuggestionListResponse,
)
from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.models import User
from app.service.user.core.database import get_db as get_db_custom
from app.service.user import suggestion as suggestion_service

router = APIRouter()


def _client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("/suggestions", response_model=SuggestionCreateResponse)
async def submit_suggestion(
    payload: SuggestionCreate,
    request: Request,
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(get_current_user),
):
    try:
        row = suggestion_service.create_suggestion(
            db,
            payload,
            user,
            submitter_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        return {
            "success": True,
            "id": row.id,
            "message": "建议已提交",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"提交建议失败: {str(exc)}")


@router.get("/suggestions/my", response_model=SuggestionListResponse)
async def get_my_suggestions(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(get_current_user),
):
    if user is None:
        raise HTTPException(status_code=401, detail="請先登錄")

    try:
        return suggestion_service.list_user_suggestions(
            db,
            user,
            status=status,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取建议列表失败: {str(exc)}")
