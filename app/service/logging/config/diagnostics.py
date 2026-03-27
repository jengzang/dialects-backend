"""Configuration for API diagnostic event capture."""

from __future__ import annotations

DIAGNOSTIC_INCLUDE_PREFIXES = (
    "/api/",
    "/auth/",
    "/sql/",
    "/admin/",
)

DIAGNOSTIC_EXCLUDE_PATTERNS = (
    "/__ping",
    "/docs",
    "/docs/*",
    "/openapi.json",
    "/statics/*",
)

SLOW_API_THRESHOLD_MS = 10_000

DIAGNOSTIC_HEADER_ALLOWLIST = (
    "content-type",
    "content-length",
    "accept",
    "origin",
    "referer",
    "authorization",
    "cookie",
    "x-forwarded-for",
    "x-real-ip",
)

DIAGNOSTIC_REDACT_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "password",
    "new_password",
    "token",
    "refresh_token",
    "access_token",
    "secret",
    "api_key",
}

MAX_DIAGNOSTIC_BODY_BYTES = 16 * 1024
MAX_DIAGNOSTIC_STACK_BYTES = 16 * 1024
MAX_DIAGNOSTIC_RESPONSE_PREVIEW_BYTES = 4 * 1024

DIAGNOSTIC_BODY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

