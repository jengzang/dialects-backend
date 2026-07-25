import json
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.service.vocabulary.models import VocabularyLog


def record_vocabulary_log(
    *,
    session: Session,
    user_id: int,
    permission_level: str,
    source: str,
    action: str,
    table_name: str,
    target_scope: str,
    affected_rows: int,
    status: str = "success",
    payload: dict[str, Any] | None = None,
    operation_id: str | None = None,
) -> VocabularyLog:
    log = VocabularyLog(
        operation_id=operation_id or str(uuid4()),
        user_id=user_id,
        permission_level=permission_level,
        source=source,
        action=action,
        table_name=table_name,
        target_scope=target_scope,
        affected_rows=affected_rows,
        status=status,
        payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str),
    )
    session.add(log)
    return log
