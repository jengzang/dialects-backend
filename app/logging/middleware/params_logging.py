"""
Request parameter logging middleware.
"""
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging.middleware.traffic_logging import (
    log_all_fields,
    update_hourly_daily_stats,
    _capture_request_body,
)
from app.logging.utils.route_matcher import match_route_config, should_skip_route


class ApiLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        max_logged_body_size = 64 * 1024

        if should_skip_route(path):
            return await call_next(request)

        try:
            update_hourly_daily_stats(path)
        except Exception as e:
            print(f"[ERROR] update_hourly_daily_stats failed: {e}")

        config = match_route_config(path)
        if not config.get("log_params") and not config.get("log_body"):
            return await call_next(request)

        params_to_log = {}

        if config.get("log_params") and request.query_params:
            params_to_log.update(dict(request.query_params))

        if config.get("log_body") and request.method in ["POST", "PUT", "PATCH"]:
            try:
                content_type = (request.headers.get("Content-Type") or "").lower()
                content_length = request.headers.get("Content-Length")
                body_len = int(content_length) if content_length and content_length.isdigit() else None

                should_log_body = (
                    "application/json" in content_type
                    and (body_len is None or body_len <= max_logged_body_size)
                )

                if should_log_body:
                    body = await _capture_request_body(request)
                    if body and len(body) <= max_logged_body_size:
                        try:
                            body_data = json.loads(body)
                            if isinstance(body_data, dict):
                                params_to_log.update(body_data)
                            else:
                                params_to_log["_body_type"] = type(body_data).__name__
                        except json.JSONDecodeError:
                            params_to_log["_raw_body"] = body.decode("utf-8", errors="ignore")
            except Exception as e:
                print(f"[WARN] request body logging failed: {e}")

        if params_to_log:
            try:
                log_all_fields(path, params_to_log)
            except Exception as e:
                print(f"[ERROR] log_all_fields failed: {e}")


        response = await call_next(request)
        return response
