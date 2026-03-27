from queue import Empty

from sqlalchemy.orm import Session

from app.common.time_utils import now_utc_naive, to_shanghai_bucket_date
from app.service.logging.core.database import SessionLocal as LogsSessionLocal
from app.service.logging.core.queues import enqueue_with_backpressure, html_visit_queue


def update_html_visit(path: str):
    """Enqueue one HTML visit event for aggregation."""
    today = now_utc_naive()
    enqueue_with_backpressure(html_visit_queue, (path, today), "html_visit_queue")


def html_visit_writer():
    """Background worker that batches HTML visit statistics updates."""
    batch = []
    batch_size = 20
    batch_timeout = 5.0

    while True:
        try:
            item = html_visit_queue.get(timeout=batch_timeout)
            if item is None:
                break

            batch.append(item)

            if len(batch) >= batch_size:
                process_html_visit_batch(batch)
                batch = []

        except Empty:
            if batch:
                process_html_visit_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] html_visit_writer failed: {e}")

    if batch:
        process_html_visit_batch(batch)


def process_html_visit_batch(batch: list):
    """Batch process HTML visit statistics updates."""
    db = LogsSessionLocal()
    try:
        for path, date_obj in batch:
            update_html_visit_stat(db, path, None)
            update_html_visit_stat(db, path, to_shanghai_bucket_date(date_obj))

        db.commit()
        print(f"[OK] flushed {len(batch)} HTML visit rows")
    except Exception as e:
        print(f"[X] failed to flush HTML visit batch: {e}")
        db.rollback()
    finally:
        db.close()


def update_html_visit_stat(db: Session, path: str, date):
    """Upsert one HTML visit statistic row."""
    from sqlalchemy import text

    try:
        result = db.execute(
            text("""
                UPDATE api_visit_log
                SET count = count + 1, updated_at = datetime('now')
                WHERE path = :path AND (
                    (date IS NULL AND :date IS NULL) OR
                    (date = :date)
                )
            """),
            {"path": path, "date": date}
        )

        if result.rowcount == 0:
            db.execute(
                text("""
                    INSERT OR IGNORE INTO api_visit_log (path, date, count, updated_at)
                    VALUES (:path, :date, 1, datetime('now'))
                """),
                {"path": path, "date": date}
            )
    except Exception as e:
        print(f"[X] failed to upsert HTML visit stat: path={path}, date={date}, error={e}")
        raise
