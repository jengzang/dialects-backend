import json
from typing import Optional

from sqlalchemy.orm import Session

from app.common.time_utils import now_utc_naive
from app.schemas.user.suggestions import SuggestionCreate
from app.service.auth.database.models import User
from app.service.user.core.models import UserSuggestion


ALLOWED_STATUSES = {"open", "reviewing", "accepted", "rejected", "done"}
ALLOWED_CATEGORIES = {"general", "bug", "feature", "data_issue", "ui"}
ALLOWED_PRIORITIES = {"low", "normal", "high"}
TERMINAL_STATUSES = {"accepted", "rejected", "done"}


def _validate_status(status: Optional[str]) -> None:
    if status is not None and status not in ALLOWED_STATUSES:
        raise ValueError("invalid status")


def _validate_category(category: Optional[str]) -> None:
    if category is not None and category not in ALLOWED_CATEGORIES:
        raise ValueError("invalid category")


def _validate_priority(priority: Optional[str]) -> None:
    if priority is not None and priority not in ALLOWED_PRIORITIES:
        raise ValueError("invalid priority")


def serialize_suggestion(row: UserSuggestion) -> dict:
    context = None
    if row.context_json:
        try:
            context = json.loads(row.context_json)
        except json.JSONDecodeError:
            context = None

    return {
        "id": row.id,
        "user_id": row.user_id,
        "username": row.username,
        "title": row.title,
        "content": row.content,
        "category": row.category,
        "source_path": row.source_path,
        "context": context,
        "contact": row.contact,
        "status": row.status,
        "priority": row.priority,
        "admin_note": row.admin_note,
        "handled_by": row.handled_by,
        "handled_by_username": row.handled_by_username,
        "handled_at": row.handled_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def create_suggestion(
    db: Session,
    data: SuggestionCreate,
    user: Optional[User] = None,
    *,
    submitter_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> UserSuggestion:
    context_json = None
    if data.context is not None:
        context_json = json.dumps(data.context, ensure_ascii=False)

    row = UserSuggestion(
        user_id=getattr(user, "id", None) if user else None,
        username=getattr(user, "username", None) if user else None,
        title=data.title,
        content=data.content,
        category=data.category,
        source_path=data.source_path,
        context_json=context_json,
        contact=data.contact,
        submitter_ip=submitter_ip,
        user_agent=user_agent,
        status="open",
        priority="normal",
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise


def list_user_suggestions(
    db: Session,
    user: User,
    *,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    _validate_status(status)
    query = db.query(UserSuggestion).filter(UserSuggestion.user_id == user.id)
    if status:
        query = query.filter(UserSuggestion.status == status)

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
        "items": [serialize_suggestion(row) for row in rows],
    }


def mark_terminal_handler(row: UserSuggestion, admin_user: User) -> None:
    row.handled_by = admin_user.id
    row.handled_by_username = admin_user.username
    row.handled_at = now_utc_naive()
