import json
from typing import Optional

from sqlalchemy.orm import Session

from app.common.time_utils import now_utc_naive
from app.schemas.user.suggestions import SuggestionCreate
from app.service.auth.database.models import ApiUsageLog, User
from app.service.user.core.models import UserSuggestion


ALLOWED_STATUSES = {"open", "reviewing", "accepted", "rejected", "done"}
ALLOWED_PRIORITIES = {"low", "normal", "high"}
TERMINAL_STATUSES = {"accepted", "rejected", "done"}
RECENT_API_LIMIT = 10


def _validate_status(status: Optional[str]) -> None:
    if status is not None and status not in ALLOWED_STATUSES:
        raise ValueError("invalid status")


def _validate_priority(priority: Optional[str]) -> None:
    if priority is not None and priority not in ALLOWED_PRIORITIES:
        raise ValueError("invalid priority")


def serialize_suggestion(row: UserSuggestion, *, include_image: bool = False) -> dict:
    context = None
    if row.context_json:
        try:
            context = json.loads(row.context_json)
        except json.JSONDecodeError:
            context = None

    recent_api = []
    if row.recent_api:
        try:
            parsed_recent_api = json.loads(row.recent_api)
            if isinstance(parsed_recent_api, list):
                recent_api = parsed_recent_api
        except json.JSONDecodeError:
            recent_api = []

    item = {
        "id": row.id,
        "user_id": row.user_id,
        "username": row.username,
        "title": row.title,
        "content": row.content,
        "category": row.category,
        "source_path": row.source_path,
        "context": context,
        "contact": row.contact,
        "recent_api": recent_api,
        "status": row.status,
        "priority": row.priority,
        "admin_note": row.admin_note,
        "handled_at": row.handled_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if include_image:
        item["image_base64"] = row.image_base64
    return item


def _serialize_api_log(row: ApiUsageLog) -> dict:
    return {
        "name": row.path,
        "time": row.called_at.isoformat() if row.called_at else None,
        "duration": row.duration,
    }


def build_recent_api_snapshot(
    auth_db: Optional[Session],
    *,
    user_id: Optional[int],
    submitter_ip: Optional[str],
    limit: int = RECENT_API_LIMIT,
) -> list[dict]:
    if auth_db is None:
        return []

    selected: list[ApiUsageLog] = []
    selected_ids: set[int] = set()

    def add_rows(rows):
        for row in rows:
            if row.id in selected_ids:
                continue
            selected.append(row)
            selected_ids.add(row.id)
            if len(selected) >= limit:
                break

    if user_id is not None:
        rows = auth_db.query(ApiUsageLog).filter(
            ApiUsageLog.user_id == user_id
        ).order_by(
            ApiUsageLog.called_at.desc(),
            ApiUsageLog.id.desc(),
        ).limit(limit).all()
        add_rows(rows)

    if submitter_ip and len(selected) < limit:
        rows = auth_db.query(ApiUsageLog).filter(
            ApiUsageLog.ip == submitter_ip
        ).order_by(
            ApiUsageLog.called_at.desc(),
            ApiUsageLog.id.desc(),
        ).limit(limit).all()
        add_rows(rows)

    return [_serialize_api_log(row) for row in selected[:limit]]


def create_suggestion(
    db: Session,
    data: SuggestionCreate,
    user: Optional[User] = None,
    *,
    auth_db: Optional[Session] = None,
    submitter_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> UserSuggestion:
    context_json = None
    if data.context is not None:
        context_json = json.dumps(data.context, ensure_ascii=False)

    user_id = getattr(user, "id", None) if user else None
    try:
        recent_api = build_recent_api_snapshot(
            auth_db,
            user_id=user_id,
            submitter_ip=submitter_ip,
        )
    except Exception:
        recent_api = []

    row = UserSuggestion(
        user_id=user_id,
        username=getattr(user, "username", None) if user else None,
        title=data.title,
        content=data.content,
        category=data.category,
        source_path=data.source_path,
        context_json=context_json,
        contact=data.contact,
        image_base64=data.image_base64,
        submitter_ip=submitter_ip,
        user_agent=user_agent,
        recent_api=json.dumps(recent_api, ensure_ascii=False),
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
    _ = admin_user
    row.handled_at = now_utc_naive()
