import traceback
import time
from datetime import datetime

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.common.api_config import MAX_ANONYMOUS_SIZE, MAX_USER_SIZE
from app.service.auth.core.dependencies import get_current_user_for_middleware
from app.service.auth.database.connection import get_db
from app.service.logging.config import ENABLE_API_KEYWORD_LOGGING
from app.service.logging.config.diagnostics import (
    DIAGNOSTIC_BODY_METHODS,
    DIAGNOSTIC_CAPTURE_MODE,
    SLOW_API_THRESHOLD_MS,
)
from app.service.logging.core.queues import (
    enqueue_with_backpressure as _enqueue_with_backpressure,
    log_queue,
    summary_queue,
)
from app.service.logging.core.workers import start_api_logger_workers, stop_api_logger_workers
from app.service.logging.stats.diagnostic_pipeline import enqueue_diagnostic_event_non_blocking
from app.service.logging.stats.html_visit_pipeline import update_html_visit
from app.service.logging.stats.keyword_pipeline import log_all_fields
from app.service.logging.stats.online_time_pipeline import enqueue_online_time_non_blocking
from app.service.logging.stats.usage_pipeline import normalize_api_path, update_count
from app.service.logging.utils.diagnostics import (
    normalize_diagnostic_route,
    serialize_diagnostic_headers,
    serialize_query_params,
    should_capture_diagnostic_path,
    summarize_request_body,
    summarize_response_preview,
    summarize_stack_trace,
)
from app.service.logging.utils.request_capture import (
    attach_diagnostic_body_capture,
    capture_request_body as _capture_request_body,
)
from app.service.logging.utils.route_matcher import match_route_config, should_skip_route
from app.service.logging.utils.usage_paths import normalize_auth_usage_path, should_record_auth_usage


async def _log_params_if_needed(request: Request, path: str):
    """
    Keep a compatibility wrapper here so legacy monkeypatch-based diagnostics tests
    can still override route matching and body capture at the middleware module level.
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
            body = await _capture_request_body(request)
            if body:
                try:
                    import json

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

    from app.common.time_utils import now_utc_naive
    from app.service.logging.core.models import ApiDiagnosticEvent
    from app.service.logging.stats.diagnostic_pipeline import build_diagnostic_notes

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
    from app.service.auth.database.models import ApiUsageLog

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

    _enqueue_with_backpressure(log_queue, log, "log_queue")

    if user_id and include_summary:
        _enqueue_with_backpressure(
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
    import asyncio

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


class StreamingResponseWrapper:
    """Wrap a streaming response so we can cap and measure output size."""

    def __init__(
        self,
        iterator,
        content_type,
        user_role,
        max_size,
        response,
        on_complete_callback=None,
    ):
        self.iterator = iterator
        self.content_type = content_type
        self.user_role = user_role
        self.max_size = max_size
        self.response = response
        self.total_size = 0
        self.on_complete_callback = on_complete_callback
        self.response_started = False
        self.response_completed = False
        self.exception = None
        self.preview_bytes = bytearray()

    async def __aiter__(self):
        """Iterate streamed chunks while tracking response size."""
        self.response_started = True
        try:
            async for chunk in self.iterator:
                chunk_bytes = chunk.encode("utf-8") if isinstance(chunk, str) else chunk
                chunk_size = len(chunk_bytes)
                self.total_size += chunk_size
                if len(self.preview_bytes) < 4096:
                    remaining = 4096 - len(self.preview_bytes)
                    self.preview_bytes.extend(chunk_bytes[:remaining])
                if self.total_size > self.max_size:
                    raise HTTPException(
                        status_code=413,
                        detail="Response body exceeds the size limit. Please narrow the request and try again."
                    )

                yield chunk
            self.response_completed = True
        except Exception as exc:
            self.exception = exc
            raise
        finally:
            if self.on_complete_callback:
                await self.on_complete_callback(self)


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        path = request.url.path
        method = request.method.upper()
        capture_diagnostics = should_capture_diagnostic_path(path)
        record_auth_usage = should_record_auth_usage(path)
        should_include_summary = path != "/api/auth/login"

        try:
            update_count(path)
        except Exception as e:
            print(f"[ERROR] failed to enqueue usage count: {e}")

        await _log_params_if_needed(request, path)
        if not capture_diagnostics and not record_auth_usage:
            return await call_next(request)

        user = None
        if capture_diagnostics or record_auth_usage:
            db = next(get_db())
            try:
                user = await get_current_user_for_middleware(request, db=db)
            except Exception as e:
                print(f"Middleware Auth Error: {e}")
                user = None
            finally:
                db.close()

        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        referer = request.headers.get("Referer")
        content_type = request.headers.get("Content-Type", "")
        content_length = request.headers.get("Content-Length")
        request_body_text = ""
        request_body_truncated = False
        diagnostic_body_state = None
        resolved_diagnostic_body = False

        should_capture_request_body = capture_diagnostics and method in DIAGNOSTIC_BODY_METHODS
        if should_capture_request_body:
            diagnostic_body_state = attach_diagnostic_body_capture(request)

        if content_length is not None and content_length.isdigit():
            request_size = int(content_length)
        elif method == "GET":
            request_size = len(request.url.path) + len(request.url.query)
        else:
            request_size = 0

        if capture_diagnostics:
            request_headers_json = serialize_diagnostic_headers(request.headers)
            query_params_json = serialize_query_params(request.scope.get("query_string", b""))
        else:
            request_headers_json = ""
            query_params_json = ""

        def resolve_diagnostic_request_body():
            nonlocal request_body_text, request_body_truncated, request_size, resolved_diagnostic_body

            if resolved_diagnostic_body or not capture_diagnostics:
                return

            resolved_diagnostic_body = True
            if diagnostic_body_state is None:
                request_body_text = ""
                request_body_truncated = False
                return

            request_body, body_capture_truncated, captured_body_size = diagnostic_body_state()
            if request_size == 0 and captured_body_size:
                request_size = captured_body_size

            if request_body:
                request_body_text, summarize_truncated = summarize_request_body(
                    request_body,
                    content_type,
                    request_size,
                )
                request_body_truncated = body_capture_truncated or summarize_truncated
            else:
                request_body_text = ""
                request_body_truncated = False

        try:
            response = await call_next(request)
        except Exception as exc:
            duration = time.time() - start_time
            duration_ms = int(round(duration * 1000))
            stack_trace_text = summarize_stack_trace(traceback.format_exc())
            status_code = 500

            if record_auth_usage:
                await log_detailed_api_to_db_async(
                    path=path,
                    duration=duration,
                    status_code=status_code,
                    ip=client_ip,
                    user_agent=user_agent,
                    referer=referer,
                    user_id=user.id if user else None,
                    request_size=request_size,
                    response_size=0,
                    start_time=start_time,
                    include_summary=should_include_summary,
                )

            if capture_diagnostics:
                resolve_diagnostic_request_body()
                enqueue_diagnostic_event(
                    path=path,
                    method=method,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    user_id=user.id if user else None,
                    username=getattr(user, "username", None),
                    ip=client_ip,
                    user_agent=user_agent,
                    referer=referer,
                    request_headers_json=request_headers_json,
                    query_params_json=query_params_json,
                    request_body_text=request_body_text,
                    request_body_truncated=request_body_truncated,
                    request_size=request_size,
                    response_size=0,
                    response_started=False,
                    response_completed=False,
                    phase_hint="exception_before_response",
                    exception_type=exc.__class__.__name__,
                    exception_message=str(exc),
                    stack_trace_text=stack_trace_text,
                    response_preview_text="",
                    content_type=content_type,
                )

            raise

        if record_auth_usage:
            max_size = MAX_ANONYMOUS_SIZE if user is None else (
                float("inf") if user.role == "admin" else MAX_USER_SIZE
            )
        else:
            max_size = float("inf")

        async def on_streaming_complete(wrapper):
            duration = time.time() - start_time
            duration_ms = int(round(duration * 1000))
            response_size = wrapper.total_size
            effective_status_code = response.status_code
            exception_type = None
            exception_message = None
            stack_trace_text = ""
            response_preview_text = ""
            phase_hint = "completed"

            if wrapper.exception is not None:
                exception_type = wrapper.exception.__class__.__name__
                exception_message = str(wrapper.exception)
                if isinstance(wrapper.exception, HTTPException):
                    effective_status_code = wrapper.exception.status_code
                elif effective_status_code < 400:
                    effective_status_code = 500
                stack_trace_text = summarize_stack_trace(
                    "".join(
                        traceback.format_exception(
                            wrapper.exception.__class__,
                            wrapper.exception,
                            wrapper.exception.__traceback__,
                        )
                    )
                )
                phase_hint = "streaming"

            if effective_status_code >= 400:
                response_preview_text = summarize_response_preview(
                    bytes(wrapper.preview_bytes),
                    response.headers.get("Content-Type", ""),
                )

            if record_auth_usage:
                await log_detailed_api_to_db_async(
                    path=path,
                    duration=duration,
                    status_code=effective_status_code,
                    ip=client_ip,
                    user_agent=user_agent,
                    referer=referer,
                    user_id=user.id if user else None,
                    request_size=request_size,
                    response_size=response_size,
                    start_time=start_time,
                    include_summary=should_include_summary,
                )

            if capture_diagnostics:
                resolve_diagnostic_request_body()
                enqueue_diagnostic_event(
                    path=path,
                    method=method,
                    status_code=effective_status_code,
                    duration_ms=duration_ms,
                    user_id=user.id if user else None,
                    username=getattr(user, "username", None),
                    ip=client_ip,
                    user_agent=user_agent,
                    referer=referer,
                    request_headers_json=request_headers_json,
                    query_params_json=query_params_json,
                    request_body_text=request_body_text,
                    request_body_truncated=request_body_truncated,
                    request_size=request_size,
                    response_size=response_size,
                    response_started=wrapper.response_started,
                    response_completed=wrapper.response_completed,
                    phase_hint=phase_hint,
                    exception_type=exception_type,
                    exception_message=exception_message,
                    stack_trace_text=stack_trace_text,
                    response_preview_text=response_preview_text,
                    content_type=response.headers.get("Content-Type", ""),
                )

        wrapper = StreamingResponseWrapper(
            iterator=response.body_iterator,
            content_type=response.headers.get("Content-Type", ""),
            user_role=user.role if user else None,
            max_size=max_size,
            response=response,
            on_complete_callback=on_streaming_complete,
        )

        response.body_iterator = wrapper
        return response
