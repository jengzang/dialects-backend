import re
from queue import Empty

from app.common.time_utils import now_utc_naive, to_shanghai_bucket_date, to_shanghai_bucket_hour
from app.service.logging.core.database import SessionLocal as LogsSessionLocal
from app.service.logging.core.queues import enqueue_with_backpressure, statistics_queue

# Static file extensions served from the app/statics directory.
_STATIC_EXTENSIONS = frozenset({
    ".js", ".mjs", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico",
    ".gif", ".webp", ".avif", ".woff", ".woff2", ".ttf", ".otf",
    ".map", ".json", ".xml", ".txt", ".xlsx", ".kmz", ".wasm",
    ".webmanifest",
})

# Content-hash pattern: name.[8+ base64url chars with >=1 letter].ext
# The (?!\d+\.) prevents date stamps (20260624) from being treated as hashes.
_CONTENT_HASH_RE = re.compile(
    r"^(.+?)\.(?!\d+\.)[A-Za-z0-9_-]{8,}\.(%s)$"
    % "|".join(
        ext.lstrip(".")
        for ext in sorted(_STATIC_EXTENSIONS, key=len, reverse=True)
    )
)

def normalize_content_hash_path(path: str) -> str:
    """Strip a Vite/Rollup content hash from a static-file path.

    ``/assets/ToolsPage.ozFry4P6.js`` → ``/assets/ToolsPage.{hash}.js``
    """
    m = _CONTENT_HASH_RE.match(path)
    if m is None:
        return path
    return f"{m.group(1)}.{{hash}}.{m.group(2)}"


def normalize_api_path(path: str) -> str:
    """
    Normalize paths for route-level statistics.

    Applies two transforms:
    1. Replace dynamic API path segments with template placeholders.
    2. Strip Vite/Rollup content hashes from static file paths.
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
        ('/api/vocabulary/locations/', '{location_name}'),
        ('/api/vocabulary/admin/permissions/', '{user_id}'),
        ('/api/vocabulary/sql/distinct/', '{table_name}/{column_name}'),
        ('/sql/distinct/', '{table_name}/{column_name}'),
    ]

    path_templates.sort(key=lambda x: len(x[0]), reverse=True)

    for prefix, param_name in path_templates:
        if path.startswith(prefix):
            suffix = path[len(prefix):]
            if not suffix:
                return normalize_content_hash_path(path)
            param_segments = param_name.count('/') + 1
            suffix_parts = suffix.split('/')
            if len(suffix_parts) <= param_segments:
                return normalize_content_hash_path(f"{prefix}{param_name}")
            rest = '/'.join(suffix_parts[param_segments:])
            return normalize_content_hash_path(f"{prefix}{param_name}/{rest}")

    return normalize_content_hash_path(path)


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
