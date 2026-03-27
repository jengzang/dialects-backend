import asyncio
from datetime import datetime
from decimal import Decimal
from queue import Empty

from sqlalchemy.orm import Session

from app.service.auth.database.connection import SessionLocal as AuthSessionLocal
from app.service.auth.database.models import ApiUsageLog, ApiUsageSummary
from app.service.logging.core.queues import enqueue_with_backpressure, log_queue, summary_queue
from app.service.logging.utils.usage_paths import normalize_auth_usage_path


def log_writer_thread():
    """Batch-write ApiUsageLog rows into auth.db."""
    db = AuthSessionLocal()

    try:
        batch = []
        batch_size = 50
        batch_timeout = 120.0

        while True:
            try:
                item = log_queue.get(timeout=batch_timeout)

                if item is None:
                    break

                batch.append(item)

                if len(batch) >= batch_size:
                    write_log_batch(db, batch)
                    batch = []

            except Empty:
                if batch:
                    write_log_batch(db, batch)
                    batch = []
            except Exception as e:
                print(f"[X] log_writer_thread failed: {e}")

        if batch:
            write_log_batch(db, batch)
    finally:
        db.close()


def write_log_batch(db: Session, batch: list):
    """Flush one ApiUsageLog batch to the database."""
    try:
        db.bulk_save_objects(batch)
        db.commit()
        print(f"[OK] Batch wrote {len(batch)} ApiUsageLog rows")
    except Exception as e:
        print(f"[X] failed to write ApiUsageLog batch: {e}")
        db.rollback()


def log_detailed_api_to_db(
    path: str,
    duration: float,
    status_code: int,
    ip: str,
    user_agent: str,
    referer: str,
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
        called_at=datetime.utcfromtimestamp(start_time) if start_time else None
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
    ip: str,
    user_agent: str,
    referer: str,
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
    batch = []
    batch_size = 50
    batch_timeout = 60.0

    while True:
        try:
            item = summary_queue.get(timeout=batch_timeout)

            if item is None:
                break

            batch.append(item)

            if len(batch) >= batch_size:
                process_summary_batch(batch)
                batch = []

        except Empty:
            if batch:
                process_summary_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] summary_writer failed: {e}")

    if batch:
        process_summary_batch(batch)


def process_summary_batch(batch: list):
    """Aggregate and write ApiUsageSummary rows in batch."""
    db = AuthSessionLocal()

    try:
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
                summary.last_updated = datetime.utcnow()
            else:
                summary = ApiUsageSummary(
                    user_id=user_id,
                    path=path,
                    count=stats["count"],
                    total_duration=Decimal(round(stats["total_duration"], 2)),
                    total_upload=Decimal(round(stats["total_upload"], 2)),
                    total_download=Decimal(round(stats["total_download"], 2)),
                    last_updated=datetime.utcnow()
                )
                db.add(summary)

        db.commit()
        print(f"[OK] flushed {len(aggregated)} ApiUsageSummary rows")
    except Exception as e:
        print(f"[X] ApiUsageSummary batch failed: {e}")
        db.rollback()
    finally:
        db.close()
