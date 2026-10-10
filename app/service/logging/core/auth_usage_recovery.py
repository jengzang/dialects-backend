"""Preserve failed auth usage events for manual reconciliation, never auto-replay."""

import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from app.common.path import BASE_DIR
from app.common.time_utils import now_utc_naive


logger = logging.getLogger(__name__)
AUTH_USAGE_QUEUE_NAMES = frozenset({"log_queue", "summary_queue"})


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported recovery value: {type(value).__name__}")


def preserve_auth_usage(queue_name: str, events: list, *, reason: str, error=None) -> Path:
    """Publish a private, fsynced JSON file; raise if preservation itself fails."""
    if queue_name not in AUTH_USAGE_QUEUE_NAMES:
        raise ValueError(f"Unsupported auth usage queue: {queue_name}")
    serialized = []
    for item in events:
        if isinstance(item, dict):
            serialized.append(dict(item))
        else:
            serialized.append({
                column.name: getattr(item, column.name)
                for column in item.__table__.columns if column.name != "id"
            })
    content = json.dumps({
        "version": 1,
        "queue_name": queue_name,
        "reason": reason,
        "saved_at": now_utc_naive().isoformat(),
        "error": str(error) if error is not None else None,
        "events": serialized,
    }, ensure_ascii=False, default=_json_value)
    directory = Path(os.environ.get(
        "AUTH_USAGE_RECOVERY_DIR", str(Path(BASE_DIR) / "logs" / "auth-usage-recovery")
    ))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = directory / f"{queue_name}-{uuid4().hex}.json"
    temporary = destination.with_suffix(".tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        try:
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # The file is already published: retrying the DB batch here could
            # commit it while leaving a misleading recovery file behind.
            logger.warning(
                "[AUTH_USAGE_RECOVERY_SYNC] %s published, but directory sync failed; power-loss durability reduced",
                destination, exc_info=True,
            )
    finally:
        temporary.unlink(missing_ok=True)
    logger.error(
        "[AUTH_USAGE_RECOVERY] Preserved %s events from %s (%s) in %s; manual reconciliation required",
        len(events), queue_name, reason, destination,
    )
    return destination
