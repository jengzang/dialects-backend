import json
from queue import Empty

from fastapi import Request

from app.common.time_utils import now_utc_naive
from app.service.logging.config import ENABLE_API_KEYWORD_LOGGING
from app.service.logging.core.database import SessionLocal as LogsSessionLocal
from app.service.logging.core.models import ApiKeywordLog
from app.service.logging.core.queues import enqueue_with_backpressure, keyword_log_queue
from app.service.logging.utils.request_capture import capture_request_body
from app.service.logging.utils.route_matcher import match_route_config, should_skip_route


async def log_params_if_needed(request: Request, path: str):
    """
    Keep legacy logs.db parameter logging logic:
    - route-based params/body logging
    """
    if not ENABLE_API_KEYWORD_LOGGING:
        return

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
            body = await capture_request_body(request)
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
    enqueue_with_backpressure(keyword_log_queue, log, "keyword_log_queue")


def log_all_fields(path: str, param_dict: dict):
    """Log all request fields for keyword statistics."""
    for field, value in param_dict.items():
        if value is not None and value != [] and value != "":
            log_keyword(path, field, value)


def keyword_log_writer():
    """Background worker that batches keyword log rows to logs.db."""
    batch = []
    batch_size = 50

    while True:
        try:
            item = keyword_log_queue.get(timeout=1)
            if item is None:
                break

            batch.append(item)

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
