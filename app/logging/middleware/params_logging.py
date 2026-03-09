"""
Backward-compatible shim for legacy imports.

The request/traffic/params logging logic is now unified in
`RequestLogMiddleware` (traffic_logging.py).
"""
from app.logging.middleware.traffic_logging import RequestLogMiddleware


class ApiLoggingMiddleware(RequestLogMiddleware):
    pass

