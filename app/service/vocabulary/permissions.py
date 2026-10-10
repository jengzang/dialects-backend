from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.service.vocabulary.models import VocabularyPermission


VALID_PERMISSION_LEVELS = {"edit", "manage", "one", "two", "three"}
SELF_SCOPED_LEVELS = {"edit", "one", "two", "three"}

_LOCATION_LIMITS: dict[str, int | None] = {
    "edit": None,
    "manage": None,
    "one": 1,
    "two": 2,
    "three": 3,
}


def get_location_limit(permission_level: str) -> int | None:
    """Return max location count for the level, or None if unlimited."""
    return _LOCATION_LIMITS.get(permission_level)


def get_effective_permission_level(db: Session, user: Optional[object]) -> str:
    if user is None:
        raise HTTPException(status_code=401, detail="請先登錄")

    if getattr(user, "role", None) == "admin":
        return "manage"

    row = db.query(VocabularyPermission).filter(
        VocabularyPermission.user_id == user.id
    ).first()
    if row is None or row.permission_level not in VALID_PERMISSION_LEVELS:
        raise HTTPException(status_code=403, detail="沒有詞表上傳權限")

    return row.permission_level
