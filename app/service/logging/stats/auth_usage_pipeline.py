import asyncio
import logging
import random
import sqlite3
import time
from datetime import datetime
from decimal import Decimal
from queue import Empty

from sqlalchemy.orm import Session

from app.common.time_utils import now_utc_naive
from app.service.auth.database.connection import SessionLocal as AuthSessionLocal
from app.service.auth.database.models import ApiUsageLog, ApiUsageSummary
from app.service.logging.core.auth_usage_recovery import preserve_auth_usage
from app.service.logging.core.queues import enqueue_with_backpressure, log_queue, summary_queue
from app.service.logging.utils.usage_paths import normalize_auth_usage_path


logger = logging.getLogger(__name__)
AUTH_USAGE_BATCH_SIZE = 50
AUTH_USAGE_BATCH_TIMEOUT_SECONDS = 2.0
AUTH_USAGE_WRITE_ATTEMPTS = 3
AUTH_USAGE_RETRY_DELAY_SECONDS = 0.1


class _RecoveryOnlyBatch(Exception):
    """An unconfirmed rollback must never cause automatic database replay."""

    def __init__(self, queue_name, error):
        super().__init__(f"Unconfirmed rollback in {queue_name}; only retry recovery storage")
        self.queue_name = queue_name
        self.error = error


def _is_sqlite_lock_error(error: Exception) -> bool:
    original = getattr(error, "orig", error)
    if not isinstance(original, sqlite3.OperationalError):
        return False
    code = getattr(original, "sqlite_errorcode", None)
    if code is not None:
        # Extended errors such as SQLITE_BUSY_SNAPSHOT share the primary code.
        return (code & 0xFF) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    return "locked" in str(original).lower() or "busy" in str(original).lower()


def _write_auth_batch(db: Session, batch: list, queue_name: str, apply) -> bool:
    """Commit or preserve a batch. If both fail, raise so the worker retains it."""
    for attempt in range(AUTH_USAGE_WRITE_ATTEMPTS):
        try:
            apply()
            db.commit()
            return True
        except Exception as error:
            try:
                db.rollback()
            except Exception:
                # Do not retry a transaction whose rollback could not be confirmed.
                logger.exception("[AUTH_USAGE] Rollback failed for %s; preserving without retry", queue_name)
                try:
                    db.close()
                except Exception:
                    logger.exception("[AUTH_USAGE] Failed to close uncertain session in %s", queue_name)
                try:
                    preserve_auth_usage(queue_name, batch, reason="rollback_failed", error=error)
                except Exception as recovery_error:
                    raise _RecoveryOnlyBatch(queue_name, error) from recovery_error
                return False
            if _is_sqlite_lock_error(error) and attempt + 1 < AUTH_USAGE_WRITE_ATTEMPTS:
                logger.warning(
                    "[AUTH_USAGE_RETRY] SQLite lock in %s; retry %s/%s after rollback",
                    queue_name, attempt + 1, AUTH_USAGE_WRITE_ATTEMPTS - 1,
                )
                delay = AUTH_USAGE_RETRY_DELAY_SECONDS * (2 ** attempt)
                time.sleep(delay * random.uniform(0.8, 1.2))
                continue
            preserve_auth_usage(queue_name, batch, reason="write_failed", error=error)
            return False


def _consume_auth_batches(q, write_batch):
    """Flush by batch size or time since first event, even with continuous arrivals."""
    batch = []
    deadline = None
    stopping = False
    recovery_only = None
    while True:
        if batch and (stopping or len(batch) >= AUTH_USAGE_BATCH_SIZE or time.monotonic() >= deadline):
            try:
                if recovery_only is not None:
                    preserve_auth_usage(
                        recovery_only.queue_name, batch, reason="rollback_failed", error=recovery_only.error,
                    )
                else:
                    write_batch(batch)
            except _RecoveryOnlyBatch as error:
                recovery_only = error
                logger.exception("[AUTH_USAGE] Retaining uncertain batch for recovery storage only")
                time.sleep(1.0)
                continue
            except Exception:
                logger.exception(
                    "[AUTH_USAGE] Database and recovery writes failed; retaining %s events in memory",
                    len(batch),
                )
                time.sleep(1.0)
                continue
            batch = []
            deadline = None
            recovery_only = None
        if stopping:
            return
        timeout = max(0.0, deadline - time.monotonic()) if batch else AUTH_USAGE_BATCH_TIMEOUT_SECONDS
        try:
            item = q.get(timeout=timeout)
        except Empty:
            continue
        if item is None:
            stopping = True
        else:
            if not batch:
                deadline = time.monotonic() + AUTH_USAGE_BATCH_TIMEOUT_SECONDS
            batch.append(item)


def log_writer_thread():
    """Batch-write ApiUsageLog rows into auth.db."""
    db = AuthSessionLocal()

    try:
        _consume_auth_batches(log_queue, lambda batch: write_log_batch(db, batch))
    finally:
        db.close()


def write_log_batch(db: Session, batch: list):
    """Flush one ApiUsageLog batch to the database."""
    return _write_auth_batch(db, batch, "log_queue", lambda: db.bulk_save_objects(batch))


def log_detailed_api_to_db(
    path: str,
    duration: float,
    status_code: int,
    ip: str | None,
    user_agent: str | None,
    referer: str | None,
    user_id: int = None,
    request_size: int = 0,
    response_size: int = 0,
    start_time: float = None,
    include_summary: bool = True,
):
    normalized_usage_path = normalize_auth_usage_path(path)

    log = ApiUsageLog(
        path=normalized_usage_path,
        duration=duration,
        status_code=status_code,
        ip=ip,
        user_agent=user_agent,
        referer=referer,
        user_id=user_id,
        request_size=request_size,
        response_size=response_size,
        called_at=datetime.utcfromtimestamp(start_time) if start_time is not None else now_utc_naive()
    )

    enqueue_with_backpressure(log_queue, log, "log_queue")

    if user_id and include_summary:
        enqueue_with_backpressure(
            summary_queue,
            {
                "user_id": user_id,
                "path": normalized_usage_path,
                "duration": duration,
                "request_size": request_size,
                "response_size": response_size,
            },
            "summary_queue"
        )


async def log_detailed_api_to_db_async(
    path: str,
    duration: float,
    status_code: int,
    ip: str | None,
    user_agent: str | None,
    referer: str | None,
    user_id: int = None,
    request_size: int = 0,
    response_size: int = 0,
    start_time: float = None,
    include_summary: bool = True,
):
    await asyncio.to_thread(
        log_detailed_api_to_db,
        path,
        duration,
        status_code,
        ip,
        user_agent,
        referer,
        user_id,
        request_size,
        response_size,
        start_time,
        include_summary,
    )


def summary_writer():
    """Batch-write ApiUsageSummary rows into auth.db."""
    _consume_auth_batches(summary_queue, process_summary_batch)


def process_summary_batch(batch: list):
    """Aggregate and write ApiUsageSummary rows in batch."""
    db = AuthSessionLocal()

    try:
        return _write_auth_batch(db, batch, "summary_queue", lambda: _apply_summary_batch(db, batch))
    finally:
        db.close()


def _apply_summary_batch(db: Session, batch: list):
    """Build summary changes afresh on every retry after rollback."""
    aggregated = {}
    for item in batch:
        normalized_path = normalize_auth_usage_path(item["path"])
        key = (item["user_id"], normalized_path)
        if key not in aggregated:
            aggregated[key] = {
                "count": 0,
                "total_duration": 0,
                "total_upload": 0,
                "total_download": 0,
            }

        aggregated[key]["count"] += 1
        aggregated[key]["total_duration"] += item["duration"]
        aggregated[key]["total_upload"] += item["request_size"] / 1024
        aggregated[key]["total_download"] += item["response_size"] / 1024

    for (user_id, path), stats in aggregated.items():
        summary = db.query(ApiUsageSummary).filter_by(
            user_id=user_id, path=path
        ).first()

        if summary:
            summary.count += stats["count"]
            summary.total_duration += Decimal(round(stats["total_duration"], 2))
            summary.total_upload += Decimal(round(stats["total_upload"], 2))
            summary.total_download += Decimal(round(stats["total_download"], 2))
            summary.last_updated = now_utc_naive()
        else:
            summary = ApiUsageSummary(
                user_id=user_id,
                path=path,
                count=stats["count"],
                total_duration=Decimal(round(stats["total_duration"], 2)),
                total_upload=Decimal(round(stats["total_upload"], 2)),
                total_download=Decimal(round(stats["total_download"], 2)),
                last_updated=now_utc_naive()
            )
            db.add(summary)
