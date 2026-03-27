from queue import Empty

from app.common.time_utils import now_utc_naive, to_shanghai_bucket_date, to_shanghai_bucket_hour
from app.service.logging.core.database import SessionLocal as LogsSessionLocal
from app.service.logging.core.queues import enqueue_with_backpressure, statistics_queue


def normalize_api_path(path: str) -> str:
    """
    Normalize dynamic API paths for route-level statistics.
    """
    path_templates = [
        ('/admin/sessions/user/', '{user_id}'),
        ('/admin/sessions/revoke-user/', '{user_id}'),
        ('/admin/sessions/revoke/', '{token_id}'),
        ('/admin/user-sessions/user/', '{user_id}'),
        ('/admin/user-sessions/revoke-user/', '{user_id}'),
        ('/admin/user-sessions/', '{session_id}'),
        ('/admin/ip/', '{api_name}/{ip}'),
        ('/api/tools/check/download/', '{task_id}'),
        ('/api/tools/jyut2ipa/download/', '{task_id}'),
        ('/api/tools/jyut2ipa/progress/', '{task_id}'),
        ('/api/tools/merge/download/', '{task_id}'),
        ('/api/tools/merge/progress/', '{task_id}'),
        ('/api/tools/praat/jobs/progress/', '{job_id}'),
        ('/api/tools/praat/uploads/progress/', '{task_id}'),
        ('/api/villages/admin/run-ids/active/', '{analysis_type}'),
        ('/api/villages/admin/run-ids/available/', '{analysis_type}'),
        ('/api/villages/admin/run-ids/metadata/', '{run_id}'),
        ('/api/villages/village/complete/', '{village_id}'),
        ('/api/villages/village/features/', '{village_id}'),
        ('/api/villages/village/ngrams/', '{village_id}'),
        ('/api/villages/village/semantic-structure/', '{village_id}'),
        ('/api/villages/village/spatial-features/', '{village_id}'),
        ('/api/villages/semantic/subcategory/chars/', '{subcategory}'),
        ('/api/villages/spatial/hotspots/', '{hotspot_id}'),
        ('/api/villages/spatial/integration/by-character/', '{character}'),
        ('/api/villages/spatial/integration/by-cluster/', '{cluster_id}'),
    ]

    path_templates.sort(key=lambda x: len(x[0]), reverse=True)

    for prefix, param_name in path_templates:
        if path.startswith(prefix):
            suffix = path[len(prefix):]
            if '/' in suffix:
                parts = suffix.split('/', 1)
                return f"{prefix}{param_name}/{parts[1]}"
            return f"{prefix}{param_name}"

    return path


def statistics_writer():
    """Background worker that batches API statistics updates."""
    batch = []
    batch_size = 100
    batch_timeout = 120.0

    while True:
        try:
            item = statistics_queue.get(timeout=batch_timeout)
            if item is None:
                break

            batch.append(item)

            if len(batch) >= batch_size:
                process_statistics_batch(batch)
                batch = []

        except Empty:
            if batch:
                process_statistics_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] statistics_writer failed: {e}")

    if batch:
        process_statistics_batch(batch)


def process_statistics_batch(batch: list):
    """Batch process usage counters with in-memory aggregation."""
    from sqlalchemy import text

    db = LogsSessionLocal()
    try:
        hourly_counts = {}
        daily_counts = {}

        for path, date_obj in batch:
            request_hour = to_shanghai_bucket_hour(date_obj)
            hourly_counts[request_hour] = hourly_counts.get(request_hour, 0) + 1

            request_date = to_shanghai_bucket_date(date_obj)
            normalized_path = normalize_api_path(path)
            daily_key = (request_date, normalized_path)
            daily_counts[daily_key] = daily_counts.get(daily_key, 0) + 1

        for hour, inc in hourly_counts.items():
            db.execute(
                text("""
                    INSERT INTO api_usage_hourly (hour, total_calls, updated_at)
                    VALUES (:hour, :inc, datetime('now'))
                    ON CONFLICT(hour) DO UPDATE SET
                        total_calls = total_calls + excluded.total_calls,
                        updated_at = datetime('now')
                """),
                {"hour": hour, "inc": inc}
            )

        for (date_key, path_key), inc in daily_counts.items():
            db.execute(
                text("""
                    INSERT INTO api_usage_daily (date, path, call_count, updated_at)
                    VALUES (:date, :path, :inc, datetime('now'))
                    ON CONFLICT(date, path) DO UPDATE SET
                        call_count = call_count + excluded.call_count,
                        updated_at = datetime('now')
                """),
                {"date": date_key, "path": path_key, "inc": inc}
            )

        db.commit()
    except Exception as e:
        print(f"[X] statistics batch failed: {e}")
        db.rollback()
    finally:
        db.close()


def update_count(path: str):
    """Enqueue one API usage event for aggregation."""
    today = now_utc_naive()
    enqueue_with_backpressure(statistics_queue, (path, today), "statistics_queue")
