import asyncio
# import gzip
# import io
import json
# import os
import threading
import multiprocessing  # Needed for cross-thread logging queues.
import time
from datetime import datetime
# from collections import defaultdict
# import ast
from decimal import Decimal
# from typing import AsyncIterable, Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
# from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from queue import Empty, Full  # multiprocessing.Queue raises queue.Full on timeout.
from app.service.auth.database.connection import get_db
from app.service.auth.core.dependencies import get_current_user_for_middleware
from app.service.auth.database.models import ApiUsageLog, ApiUsageSummary
from app.service.logging.core.database import SessionLocal as LogsSessionLocal
from app.service.logging.core.models import ApiKeywordLog
from app.common.api_config import RECORD_API, IGNORE_API, MAX_ANONYMOUS_SIZE, MAX_USER_SIZE
from app.common.time_utils import now_utc_naive, to_shanghai_bucket_date, to_shanghai_bucket_hour
from app.service.logging.utils.route_matcher import match_route_config, should_skip_route



def normalize_api_path(path: str) -> str:
    """
    Normalize dynamic API paths for route-level statistics.

    Known prefixes are converted to route templates when possible.

    Examples:
        /admin/sessions/user/123 -> /admin/sessions/user/{user_id}
        /api/tools/check/download/abc-123 -> /api/tools/check/download/{task_id}
        /api/villages/village/features/12345 -> /api/villages/village/features/{village_id}

    Args:
        path: Original API path.

    Returns:
        Normalized route path.
    """

    # Match longer prefixes first so nested routes normalize correctly.
    path_templates = [
        # Admin - Sessions
        ('/admin/sessions/user/', '{user_id}'),
        ('/admin/sessions/revoke-user/', '{user_id}'),
        ('/admin/sessions/revoke/', '{token_id}'),

        # Admin - User Sessions
        ('/admin/user-sessions/user/', '{user_id}'),
        ('/admin/user-sessions/revoke-user/', '{user_id}'),
        ('/admin/user-sessions/', '{session_id}'),

        # Admin - IP
        ('/admin/ip/', '{api_name}/{ip}'),

        # API - Tools (Check)
        ('/api/tools/check/download/', '{task_id}'),

        # API - Tools (Jyut2IPA)
        ('/api/tools/jyut2ipa/download/', '{task_id}'),
        ('/api/tools/jyut2ipa/progress/', '{task_id}'),

        # API - Tools (Merge)
        ('/api/tools/merge/download/', '{task_id}'),
        ('/api/tools/merge/progress/', '{task_id}'),

        # API - Tools (Praat)
        ('/api/tools/praat/jobs/progress/', '{job_id}'),
        ('/api/tools/praat/uploads/progress/', '{task_id}'),

        # API - Villages (Admin)
        ('/api/villages/admin/run-ids/active/', '{analysis_type}'),
        ('/api/villages/admin/run-ids/available/', '{analysis_type}'),
        ('/api/villages/admin/run-ids/metadata/', '{run_id}'),

        # API - Villages (Village)
        ('/api/villages/village/complete/', '{village_id}'),
        ('/api/villages/village/features/', '{village_id}'),
        ('/api/villages/village/ngrams/', '{village_id}'),
        ('/api/villages/village/semantic-structure/', '{village_id}'),
        ('/api/villages/village/spatial-features/', '{village_id}'),

        # API - Villages (Semantic)
        ('/api/villages/semantic/subcategory/chars/', '{subcategory}'),

        # API - Villages (Spatial)
        ('/api/villages/spatial/hotspots/', '{hotspot_id}'),
        ('/api/villages/spatial/integration/by-character/', '{character}'),
        ('/api/villages/spatial/integration/by-cluster/', '{cluster_id}'),

        # SQL

    ]

    # 鎸夊墠缂€闀垮害闄嶅簭鎺掑簭锛岀‘淇濇洿鍏蜂綋鐨勮矾寰勫厛鍖归厤
    path_templates.sort(key=lambda x: len(x[0]), reverse=True)

    for prefix, param_name in path_templates:
        if path.startswith(prefix):
            # 鎻愬彇鍓嶇紑鍚庣殑閮ㄥ垎
            suffix = path[len(prefix):]


            if '/' in suffix:

                parts = suffix.split('/', 1)
                return f"{prefix}{param_name}/{parts[1]}"
            else:
                # No trailing subpath remains after the dynamic segment.
                return f"{prefix}{param_name}"

    # No known template matched; keep the original path.
    return path


# === Queue setup ===
# Use multiprocessing.Queue so background workers can share queues safely.
# keyword_queue = queue.Queue()  # Legacy text-file queue, no longer used.
log_queue = multiprocessing.Queue(maxsize=2000)  # ApiUsageLog -> auth.db
keyword_log_queue = multiprocessing.Queue(maxsize=5000)  # ApiKeywordLog -> logs.db
statistics_queue = multiprocessing.Queue(maxsize=3000)  # API statistics -> logs.db
html_visit_queue = multiprocessing.Queue(maxsize=1000)  # HTML visit stats -> logs.db
summary_queue = multiprocessing.Queue(maxsize=1000)  # ApiUsageSummary -> auth.db
online_time_queue = multiprocessing.Queue(maxsize=1000)  # Online time reports -> auth.db

QUEUE_PUT_TIMEOUT_SECONDS = 0.05  # Backpressure wait time before dropping.


def _enqueue_with_backpressure(q, item, queue_name: str) -> bool:
    """Try enqueue with short backpressure instead of immediate drop."""
    try:
        q.put(item, timeout=QUEUE_PUT_TIMEOUT_SECONDS)
        return True
    except Full:
        print(
            f"[WARN] {queue_name} is full after {int(QUEUE_PUT_TIMEOUT_SECONDS * 1000)}ms, dropping entry"
        )
        return False


# === Request parameter logging for logs.db ===
async def _capture_request_body(request: Request) -> bytes:
    """Read request body and restore stream for downstream handlers."""
    body = await request.body()

    async def receive():
        return {"type": "http.request", "body": body}

    request._receive = receive
    return body


async def _log_params_if_needed(request: Request, path: str):
    """
    Keep legacy logs.db parameter logging logic:
    - route-based params/body logging
    """
    if should_skip_route(path):
        return

    config = match_route_config(path)
    if not config.get("log_params") and not config.get("log_body"):
        return

    params_to_log = {}

    if config.get("log_params") and request.query_params:
        params_to_log.update(dict(request.query_params))

    if config.get("log_body") and request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await _capture_request_body(request)
            if body:
                try:
                    body_data = json.loads(body)
                    if isinstance(body_data, dict):
                        params_to_log.update(body_data)
                    else:
                        params_to_log["_raw_body"] = body.decode("utf-8", errors="ignore")
                except json.JSONDecodeError:
                    params_to_log["_raw_body"] = body.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[WARN] failed to read request body for params logging: {e}")

    if params_to_log:
        try:
            log_all_fields(path, params_to_log)
        except Exception as e:
            print(f"[ERROR] failed to enqueue params logs: {e}")

def log_keyword(path: str, field: str, value):
    """Enqueue one keyword field entry for request statistics."""
    timestamp = now_utc_naive()
    log = ApiKeywordLog(
        timestamp=timestamp,
        path=path,
        field=field,
        value=str(value)
    )
    _enqueue_with_backpressure(keyword_log_queue, log, "keyword_log_queue")


def log_all_fields(path: str, param_dict: dict):
    """Log all request fields for keyword statistics."""
    for field, value in param_dict.items():
        if value is not None and value != [] and value != "":
            log_keyword(path, field, value)


# === Keyword log batch writer for logs.db ===
def keyword_log_writer():
    """Background worker that batches keyword log rows to logs.db."""
    batch = []
    batch_size = 50  # Flush every 50 records.

    while True:
        try:

            item = keyword_log_queue.get(timeout=1)
            if item is None:
                break

            batch.append(item)

            # Flush batch when threshold is reached.
            if len(batch) >= batch_size:
                db = LogsSessionLocal()
                try:
                    db.bulk_save_objects(batch)
                    db.commit()

                    batch = []
                except Exception as e:
                    print(f"[X] failed to flush keyword log batch: {e}")
                    db.rollback()
                finally:
                    db.close()

        except Empty:
            # Queue timeout: flush any pending records.
            if batch:
                db = LogsSessionLocal()
                try:
                    db.bulk_save_objects(batch)
                    db.commit()

                    batch = []
                except Exception as e:
                    print(f"[X] failed to flush keyword log batch: {e}")
                    db.rollback()
                finally:
                    db.close()
        except Exception as e:
            print(f"[X] keyword_log_writer failed: {e}")

    # Flush any remaining records before exit.
    if batch:
        db = LogsSessionLocal()
        try:
            db.bulk_save_objects(batch)
            db.commit()
        except Exception as e:
            print(f"[X] failed to flush keyword log batch: {e}")
            db.rollback()
        finally:
            db.close()



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
                _process_statistics_batch(batch)
                batch = []

        except Empty:
            # Queue timeout: flush any pending records.
            if batch:
                _process_statistics_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] statistics_writer failed: {e}")

    # Flush any remaining records before exit.
    if batch:
        _process_statistics_batch(batch)


def _process_statistics_batch_legacy(batch: list):
    """Batch process legacy statistics updates."""
    from sqlalchemy import text

    db = LogsSessionLocal()
    try:
        for path, date_obj in batch:




            result = db.execute(
                text("""
                    UPDATE api_usage_hourly
                    SET total_calls = total_calls + 1, updated_at = datetime('now')
                    WHERE hour = :hour
                """),
                {"hour": request_hour}
            )
            if result.rowcount == 0:
                db.execute(
                    text("""
                        INSERT OR IGNORE INTO api_usage_hourly (hour, total_calls)
                        VALUES (:hour, 1)
                    """),
                    {"hour": request_hour}
                )



            request_date = to_shanghai_bucket_date(date_obj)
            result = db.execute(
                text("""
                    UPDATE api_usage_daily
                    SET call_count = call_count + 1, updated_at = datetime('now')
                    WHERE date = :date AND path = :path
                """),
                {"date": request_date, "path": normalized_path}
            )
            if result.rowcount == 0:
                db.execute(
                    text("""
                        INSERT OR IGNORE INTO api_usage_daily (date, path, call_count)
                        VALUES (:date, :path, 1)
                    """),
                    {"date": request_date, "path": normalized_path}
                )

        db.commit()
        # print(f"[OK] flushed {len(batch)} statistics rows")
    except Exception as e:
        print(f"[X] failed to process statistics batch: {e}")
        db.rollback()
    finally:
        db.close()




def _process_statistics_batch(batch: list):
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
    _enqueue_with_backpressure(statistics_queue, (path, today), "statistics_queue")


def enqueue_online_time_non_blocking(data: dict):
    """
    Enqueue an online-time payload without blocking the request path.

    Args:
        data: Mapping with user_id, session_id, seconds, and timestamp.

    If the queue is full, write directly as a fallback.
    """
    try:
        online_time_queue.put_nowait(data)
    except Full:

        print(f"[!] online_time_queue is full, writing directly")
        _write_online_time_batch({
            (data['user_id'], data.get('session_id')): data
        })


def update_html_visit(path: str):
    """Enqueue one HTML visit event for aggregation."""
    today = now_utc_naive()
    _enqueue_with_backpressure(html_visit_queue, (path, today), "html_visit_queue")



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
                _process_html_visit_batch(batch)
                batch = []

        except Empty:
            # Queue timeout: flush any pending records.
            if batch:
                _process_html_visit_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] html_visit_writer failed: {e}")

    # Flush any remaining records before exit.
    if batch:
        _process_html_visit_batch(batch)


def _process_html_visit_batch(batch: list):
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
        # Try update first, then insert if the row does not exist.
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



def log_writer_thread():
    """Batch-write ApiUsageLog rows into auth.db."""
    from app.service.auth.database.connection import SessionLocal as AuthSessionLocal

    # 鍦ㄧ嚎绋嬪唴鍒涘缓鏁版嵁搴撹繛鎺ワ紙閬垮厤璺ㄨ繘绋嬩紶閫掞級
    db = AuthSessionLocal()

    try:
        batch = []
        batch_size = 50
        batch_timeout = 120.0

        while True:
            try:
                # 浣跨敤瓒呮椂绛夊緟锛岃€岄潪 sleep
                item = log_queue.get(timeout=batch_timeout)

                if item is None:
                    break

                batch.append(item)


                if len(batch) >= batch_size:
                    _write_log_batch(db, batch)
                    batch = []

            except Empty:
                # Queue timeout: flush any pending records.
                if batch:
                    _write_log_batch(db, batch)
                    batch = []
            except Exception as e:
                print(f"[X] log_writer_thread failed: {e}")

        # Flush any remaining records before exit.
        if batch:
            _write_log_batch(db, batch)
    finally:
        db.close()


def _write_log_batch(db: Session, batch: list):
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
        start_time: float = None
):
    # Step 1: build detailed log and enqueue for background writer
    log = ApiUsageLog(
        path=path,
        duration=duration,
        status_code=status_code,
        ip=ip,
        user_agent=user_agent,
        referer=referer,
        user_id=user_id,
        request_size=request_size,
        response_size=response_size,
        # Preserve request start time as a UTC naive datetime for storage.
        called_at=datetime.utcfromtimestamp(start_time) if start_time else None
    )

    # Queue the row for background persistence.
    _enqueue_with_backpressure(log_queue, log, "log_queue")

    # Step 2: enqueue ApiUsageSummary update
    if user_id:
        _enqueue_with_backpressure(
            summary_queue,
            {
                'user_id': user_id,
                'path': path,
                'duration': duration,
                'request_size': request_size,
                'response_size': response_size
            },
            "summary_queue"
        )


def summary_writer():
    """鎵归噺鏇存柊 ApiUsageSummary"""
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
                _process_summary_batch(batch)
                batch = []

        except Empty:
            if batch:
                _process_summary_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] summary_writer failed: {e}")

    if batch:
        _process_summary_batch(batch)


def _process_summary_batch(batch: list):
    """Aggregate and write ApiUsageSummary rows in batch."""
    from app.service.auth.database.connection import SessionLocal as AuthSessionLocal
    db = AuthSessionLocal()

    try:
        # Aggregate by (user_id, path) to reduce write amplification.
        aggregated = {}
        for item in batch:
            key = (item['user_id'], item['path'])
            if key not in aggregated:
                aggregated[key] = {
                    'count': 0,
                    'total_duration': 0,
                    'total_upload': 0,
                    'total_download': 0
                }

            aggregated[key]['count'] += 1
            aggregated[key]['total_duration'] += item['duration']
            aggregated[key]['total_upload'] += item['request_size'] / 1024
            aggregated[key]['total_download'] += item['response_size'] / 1024

        # Upsert aggregated summary rows.
        for (user_id, path), stats in aggregated.items():
            summary = db.query(ApiUsageSummary).filter_by(
                user_id=user_id, path=path
            ).first()

            if summary:
                summary.count += stats['count']
                summary.total_duration += Decimal(round(stats['total_duration'], 2))
                summary.total_upload += Decimal(round(stats['total_upload'], 2))
                summary.total_download += Decimal(round(stats['total_download'], 2))
                summary.last_updated = datetime.utcnow()
            else:
                summary = ApiUsageSummary(
                    user_id=user_id,
                    path=path,
                    count=stats['count'],
                    total_duration=Decimal(round(stats['total_duration'], 2)),
                    total_upload=Decimal(round(stats['total_upload'], 2)),
                    total_download=Decimal(round(stats['total_download'], 2)),
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


def online_time_writer():
    """
    Background thread: batch write online time updates
    Aggregates multiple reports for same user/session before writing
    """
    batch = {}  # {(user_id, session_id): total_seconds}
    last_write_time = time.time()
    batch_timeout = 30  # Write every 30 seconds

    while True:
        try:
            # Get item from queue with timeout
            item = online_time_queue.get(timeout=5)
            if item is None:  # Stop signal
                break

            # Aggregate by (user_id, session_id)
            key = (item['user_id'], item.get('session_id'))
            if key in batch:
                batch[key]['seconds'] += item['seconds']
            else:
                batch[key] = item

            # Write if batch is large or timeout reached
            current_time = time.time()
            should_write = (
                len(batch) >= 50 or  # Batch size limit
                (current_time - last_write_time) >= batch_timeout  # Time limit
            )

            if should_write:
                _write_online_time_batch(batch)
                batch = {}
                last_write_time = current_time

        except Empty:
            # Timeout - write remaining batch if any
            if batch:
                _write_online_time_batch(batch)
                batch = {}
                last_write_time = time.time()
        except Exception as e:
            print(f"[X] Online time writer error: {e}")

    # Write remaining batch on shutdown
    if batch:
        _write_online_time_batch(batch)


def _write_online_time_batch(batch: dict):
    """Write aggregated online time updates to database"""
    from app.service.auth.database.connection import SessionLocal as AuthSessionLocal
    from app.service.auth.database.models import User, Session

    db = AuthSessionLocal()
    try:
        for (user_id, session_id), item in batch.items():
            seconds = item['seconds']

            # Update user
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.total_online_seconds = (user.total_online_seconds or 0) + seconds
                user.last_seen = datetime.utcnow()

            # Update session if exists
            if session_id:
                session = db.query(Session).filter(
                    Session.session_id == session_id
                ).first()
                if session:
                    session.total_online_seconds = (session.total_online_seconds or 0) + seconds
                    session.last_seen = datetime.utcnow()

        db.commit()
        print(f"[OnlineTimeWriter] Batch wrote {len(batch)} online time updates")
    except Exception as e:
        print(f"[X] Failed to write online time batch: {e}")
        db.rollback()
    finally:
        db.close()


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
        start_time: float = None
):
    """Run detailed API logging in a worker thread without blocking the request."""
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
        start_time
    )


# app/service/api_logger.py
_workers_started = False
_start_lock = threading.Lock()


def start_api_logger_workers():
    """Start all background logging workers once."""
    global _workers_started
    with _start_lock:
        if _workers_started:
            return


        threading.Thread(target=keyword_log_writer, daemon=True).start()


        threading.Thread(target=statistics_writer, daemon=True).start()


        threading.Thread(target=html_visit_writer, daemon=True).start()



        threading.Thread(target=log_writer_thread, daemon=True).start()


        threading.Thread(target=summary_writer, daemon=True).start()


        threading.Thread(target=online_time_writer, daemon=True).start()

        _workers_started = True
        print("[OK] API logger workers started")


def stop_api_logger_workers():
    """Stop all background logging workers."""
    try:
        keyword_log_queue.put_nowait(None)
    except:
        pass

    try:
        statistics_queue.put_nowait(None)
    except:
        pass

    try:
        html_visit_queue.put_nowait(None)
    except:
        pass

    try:
        log_queue.put_nowait(None)
    except:
        pass

    try:
        summary_queue.put_nowait(None)
    except:
        pass

    try:
        online_time_queue.put_nowait(None)
    except:
        pass

    print("[OK] API logger workers stopped")


class StreamingResponseWrapper:
    """Wrap a streaming response so we can cap and measure output size."""

    def __init__(self, iterator, content_type, user_role, max_size, response, on_complete_callback=None):
        self.iterator = iterator
        self.content_type = content_type
        self.user_role = user_role
        self.max_size = max_size
        self.response = response
        self.total_size = 0
        self.on_complete_callback = on_complete_callback

    async def __aiter__(self):
        """Iterate streamed chunks while tracking response size."""
        try:
            async for chunk in self.iterator:
                chunk_size = len(chunk)
                self.total_size += chunk_size
                # Stop streaming once the response exceeds the configured limit.
                if self.total_size > self.max_size:
                    raise HTTPException(
                        status_code=413,
                        detail="Response body exceeds the size limit. Please narrow the request and try again."
                    )


                yield chunk

        finally:
            # Notify the completion callback after the iterator finishes.
            if self.on_complete_callback:
                await self.on_complete_callback(self)



class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()  # Capture request start time as early as possible.


        path = request.url.path
        try:
            update_count(path)
        except Exception as e:
            print(f"[ERROR] failed to enqueue usage count: {e}")

        await _log_params_if_needed(request, path)
        if any(k in path for k in IGNORE_API) or not any(k in path for k in RECORD_API):
            return await call_next(request)

        # 2. Open a DB session for auth lookup.
        # next(get_db()) is safe here because we always close it in finally.
        db = next(get_db())
        user = None
        try:

            user = await get_current_user_for_middleware(request, db=db)
        except Exception as e:
            print(f"Middleware Auth Error: {e}")

            user = None
        finally:

            db.close()

        # 5. Estimate request size.
        cl = request.headers.get("Content-Length")

        if cl is not None and cl.isdigit():
            request_size = int(cl)
        else:

            if request.method == "GET":
                url_size = len(request.url.path) + len(request.url.query)
                request_size = url_size
            else:
                # For non-GET requests we read the request body directly.
                request_body = await request.body()
                request_size = len(request_body)


        response = await call_next(request)


        max_size = MAX_ANONYMOUS_SIZE if user is None else (
            float('inf') if user.role == "admin" else MAX_USER_SIZE
        )

        # 8. Defer log persistence until streaming has completed.
        async def on_streaming_complete(wrapper):
            """Record logs after streaming responses finish."""
            # Compute duration after the full response body has been sent.
            duration = time.time() - start_time

            # Use the wrapper's tracked size for streamed responses.


            response_size = wrapper.total_size


            await log_detailed_api_to_db_async(
                path=request.url.path,
                duration=duration,
                status_code=response.status_code,
                ip=request.client.host,
                user_agent=request.headers.get("User-Agent"),
                referer=request.headers.get("Referer"),
                user_id=user.id if user else None,
                request_size=request_size,
                response_size=response_size,
                start_time=start_time
            )


        wrapper = StreamingResponseWrapper(
            iterator=response.body_iterator,
            content_type=response.headers.get("Content-Type", ""),
            user_role=user.role if user else None,
            max_size=max_size,
            response=response,
            on_complete_callback=on_streaming_complete
        )


        response.body_iterator = wrapper

        return response

# Historical JSON-file logger kept for reference.
# === Detailed response logging (legacy file-based implementation) ===
# def log_detailed_api(path, duration, status_code, ip, user_agent, referer):
#     today = now_utc_naive().strftime("%Y-%m-%d")
#     detailed_queue.put((path, duration, status_code, ip, user_agent, referer, today))
#
# # === Batch writer for detailed response logging ===
# def detailed_writer():

#     def init_stats():
#         return {
#             "count": 0, "total_time": 0.0, "status_codes": defaultdict(int),
#             "ips": set(), "agents": set(), "referers": set()
#         }
#
#     # Load persisted JSON state if it exists.
#     if os.path.exists(API_DETAILED_JSON):
#         with open(API_DETAILED_JSON, "r", encoding="utf-8") as f:
#             raw = json.load(f)
#             detailed_stats = defaultdict(init_stats, {
#                 k: {
#                     "count": v["count"],
#                     "total_time": v["total_time"],
#                     "status_codes": defaultdict(int, v["status_codes"]),
#                     "ips": set(v["ips"]),
#                     "agents": set(v["agents"]),
#                     "referers": set(v["referers"]),
#                 } for k, v in raw["detailed_stats"].items()
#             })
#             daily_stats = defaultdict(lambda: defaultdict(init_stats))
#             for date, paths in raw["daily_stats"].items():
#                 for path, v in paths.items():
#                     daily_stats[date][path] = {
#                         "count": v["count"],
#                         "total_time": v["total_time"],
#                         "status_codes": defaultdict(int, v["status_codes"]),
#                         "ips": set(v["ips"]),
#                         "agents": set(v["agents"]),
#                         "referers": set(v["referers"]),
#                     }
#     else:
#         detailed_stats = defaultdict(init_stats)
#         daily_stats = defaultdict(lambda: defaultdict(init_stats))
#
#     while True:
#         item = detailed_queue.get()
#         if item is None:
#             break
#         path, duration, status, ip, agent, referer, date = item
#
#         d = detailed_stats[path]
#         d["count"] += 1
#         d["total_time"] += duration
#         d["status_codes"][status] += 1
#         d["ips"].add(ip)
#         d["agents"].add(agent)
#         if referer:
#             d["referers"].add(referer)
#
#         d_day = daily_stats[date][path]
#         d_day["count"] += 1
#         d_day["total_time"] += duration
#         d_day["status_codes"][status] += 1
#         d_day["ips"].add(ip)
#         d_day["agents"].add(agent)
#         if referer:
#             d_day["referers"].add(referer)
#
#         # Persist the JSON snapshot after each batch.
#         with open(API_DETAILED_JSON, "w", encoding="utf-8") as f:
#             json.dump({
#                 "detailed_stats": {
#                     k: {
#                         "count": v["count"],
#                         "total_time": v["total_time"],
#                         "status_codes": dict(v["status_codes"]),
#                         "ips": list(v["ips"]),
#                         "agents": list(v["agents"]),
#                         "referers": list(v["referers"]),
#                     } for k, v in detailed_stats.items()
#                 },
#                 "daily_stats": {
#                     date: {
#                         path: {
#                             "count": v["count"],
#                             "total_time": v["total_time"],
#                             "status_codes": dict(v["status_codes"]),
#                             "ips": list(v["ips"]),
#                             "agents": list(v["agents"]),
#                             "referers": list(v["referers"]),
#                         } for path, v in paths.items()
#                     } for date, paths in daily_stats.items()
#                 }
#             }, f, ensure_ascii=False, indent=2)
#

#         with open(API_DETAILED_FILE, "w", encoding="utf-8") as f:
#             f.write("=== Total Summary ===\n")
#             for path, d in detailed_stats.items():
#                 avg = d["total_time"] / d["count"] if d["count"] else 0
#                 f.write(f"{path}\n  Count: {d['count']}\n  Avg Response Time: {avg:.3f}s\n")
#                 f.write(f"  Status Codes: {', '.join(f'{k}:{v}' for k, v in d['status_codes'].items())}\n")
#                 f.write("  IPs:\n" + ''.join(f"    - {ip}\n" for ip in sorted(d['ips'])))
#                 f.write("  User-Agents:\n" + ''.join(f"    - {ua}\n" for ua in sorted(d['agents'])))
#                 f.write("  Referers:\n" + ''.join(f"    - {r}\n" for r in sorted(d['referers'])))
#                 f.write("\n")
#             f.write("=== Daily Summary ===\n")
#             for date in sorted(daily_stats):
#                 f.write(f"{date}\n")
#                 for path, d in daily_stats[date].items():
#                     avg = d["total_time"] / d["count"] if d["count"] else 0
#                     f.write(f"{path}\n  Count: {d['count']}\n  Avg Response Time: {avg:.3f}s\n")
#                     f.write(f"  Status Codes: {', '.join(f'{k}:{v}' for k, v in d['status_codes'].items())}\n")
#                     f.write("  IPs:\n" + ''.join(f"    - {ip}\n" for ip in sorted(d['ips'])))
#                     f.write("  User-Agents:\n" + ''.join(f"    - {ua}\n" for ua in sorted(d['agents'])))
#                     f.write("  Referers:\n" + ''.join(f"    - {r}\n" for r in sorted(d['referers'])))
#                 f.write("\n")





