import json
from queue import Empty

from app.common.time_utils import now_utc_naive
from app.service.logging.config.diagnostics import DIAGNOSTIC_CAPTURE_MODE, SLOW_API_THRESHOLD_MS
from app.service.logging.core.database import SessionLocal as LogsSessionLocal
from app.service.logging.core.models import ApiDiagnosticEvent
from app.service.logging.core.queues import diagnostic_queue, enqueue_with_backpressure
from app.service.logging.utils.diagnostics import normalize_diagnostic_route


def enqueue_diagnostic_event_non_blocking(event: ApiDiagnosticEvent) -> bool:
    """Enqueue one diagnostic event without blocking the request path."""
    return enqueue_with_backpressure(diagnostic_queue, event, "diagnostic_queue")


def build_diagnostic_notes(content_type: str, *, request_size: int, response_size: int) -> str:
    payload = {
        "slow_threshold_ms": SLOW_API_THRESHOLD_MS,
        "content_type": content_type or "",
        "request_size": request_size,
        "response_size": response_size,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def diagnostic_event_writer():
    """Background worker that batches diagnostic events to logs.db."""
    batch = []
    batch_size = 25

    while True:
        try:
            item = diagnostic_queue.get(timeout=1)
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
                    print(f"[X] failed to flush diagnostic event batch: {e}")
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
                    print(f"[X] failed to flush diagnostic event batch: {e}")
                    db.rollback()
                finally:
                    db.close()
        except Exception as e:
            print(f"[X] diagnostic_event_writer failed: {e}")

    if batch:
        db = LogsSessionLocal()
        try:
            db.bulk_save_objects(batch)
            db.commit()
        except Exception as e:
            print(f"[X] failed to flush diagnostic event batch: {e}")
            db.rollback()
        finally:
            db.close()


def enqueue_diagnostic_event(
    *,
    path: str,
    method: str,
    status_code: int | None,
    duration_ms: int,
    user_id: int | None,
    username: str | None,
    ip: str | None,
    user_agent: str | None,
    referer: str | None,
    request_headers_json: str,
    query_params_json: str,
    request_body_text: str,
    request_body_truncated: bool,
    request_size: int,
    response_size: int,
    response_started: bool,
    response_completed: bool,
    phase_hint: str,
    exception_type: str | None = None,
    exception_message: str | None = None,
    stack_trace_text: str | None = None,
    response_preview_text: str | None = None,
    content_type: str = "",
):
    is_error = (status_code or 500) >= 400 or bool(exception_type)
    is_slow = duration_ms > SLOW_API_THRESHOLD_MS
    if DIAGNOSTIC_CAPTURE_MODE == "all":
        if is_error and is_slow:
            event_type = "error_and_slow"
        elif is_error:
            event_type = "error"
        elif is_slow:
            event_type = "slow"
        else:
            event_type = "normal"
    else:
        if not is_error and not is_slow:
            return
        if is_error and is_slow:
            event_type = "error_and_slow"
        elif is_error:
            event_type = "error"
        else:
            event_type = "slow"

    event = ApiDiagnosticEvent(
        occurred_at=now_utc_naive(),
        event_type=event_type,
        path=path,
        route_template=normalize_diagnostic_route(path),
        method=method,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        username=username,
        ip=ip,
        user_agent=user_agent,
        referer=referer,
        request_headers_json=request_headers_json,
        query_params_json=query_params_json,
        request_body_text=request_body_text,
        request_body_truncated=bool(request_body_truncated),
        request_size=request_size,
        response_size=response_size,
        response_started=bool(response_started),
        response_completed=bool(response_completed),
        phase_hint=phase_hint,
        exception_type=exception_type,
        exception_message=exception_message,
        stack_trace_text=stack_trace_text,
        response_preview_text=response_preview_text,
        notes_json=build_diagnostic_notes(
            content_type,
            request_size=request_size,
            response_size=response_size,
        ),
    )
    enqueue_diagnostic_event_non_blocking(event)
