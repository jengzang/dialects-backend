from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.common.time_utils import now_utc_naive
from app.schemas.user.suggestions import AdminSuggestionUpdate
from app.service.auth.database.models import User
from app.service.user.core.models import UserSuggestion
from app.service.user.suggestion import (
    TERMINAL_STATUSES,
    _validate_status,
    mark_terminal_handler,
    serialize_suggestion,
)


def list_suggestions_admin(
    db: Session,
    *,
    status: Optional[str] = None,
    category: Optional[str] = None,
    user_id: Optional[int] = None,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    _validate_status(status)

    query = db.query(UserSuggestion)
    if status:
        query = query.filter(UserSuggestion.status == status)
    if category:
        query = query.filter(UserSuggestion.category == category)
    if user_id is not None:
        query = query.filter(UserSuggestion.user_id == user_id)
    if q:
        keyword = f"%{q.strip()}%"
        query = query.filter(
            or_(
                UserSuggestion.title.like(keyword),
                UserSuggestion.content.like(keyword),
                UserSuggestion.username.like(keyword),
                UserSuggestion.contact.like(keyword),
            )
        )

    total = query.count()
    rows = query.order_by(
        UserSuggestion.created_at.desc(),
        UserSuggestion.id.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [serialize_suggestion(row, include_image=True) for row in rows],
    }


def update_suggestion_admin(
    db: Session,
    suggestion_id: int,
    data: AdminSuggestionUpdate,
    admin_user: User,
) -> Optional[dict]:
    row = db.query(UserSuggestion).filter(UserSuggestion.id == suggestion_id).first()
    if row is None:
        return None

    fields_set = data.model_fields_set

    if "status" in fields_set and data.status is not None:
        row.status = data.status
        if data.status in TERMINAL_STATUSES:
            mark_terminal_handler(row, admin_user)
    if "priority" in fields_set and data.priority is not None:
        row.priority = data.priority
    if "admin_note" in fields_set:
        row.admin_note = data.admin_note

    row.updated_at = now_utc_naive()

    try:
        db.commit()
        db.refresh(row)
        return serialize_suggestion(row, include_image=True)
    except Exception:
        db.rollback()
        raise
