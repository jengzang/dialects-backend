"""Helpers for API diagnostic event capture."""

from __future__ import annotations

import json
from fnmatch import fnmatchcase
from typing import Any, Mapping
from urllib.parse import parse_qs

from app.service.logging.config.diagnostics import (
    DIAGNOSTIC_EXCLUDE_PATTERNS,
    DIAGNOSTIC_HEADER_ALLOWLIST,
    DIAGNOSTIC_INCLUDE_PREFIXES,
    DIAGNOSTIC_REDACT_KEYS,
    MAX_DIAGNOSTIC_BODY_BYTES,
    MAX_DIAGNOSTIC_RESPONSE_PREVIEW_BYTES,
    MAX_DIAGNOSTIC_STACK_BYTES,
)
from app.service.logging.utils.path_templates import normalize_route_path


def should_capture_diagnostic_path(path: str) -> bool:
    """Return True when the request path should participate in diagnostics."""
    if any(fnmatchcase(path, pattern) for pattern in DIAGNOSTIC_EXCLUDE_PATTERNS):
        return False
    return any(path.startswith(prefix) for prefix in DIAGNOSTIC_INCLUDE_PREFIXES)


def normalize_diagnostic_route(path: str) -> str:
    """Normalize a concrete path into a stable route template for diagnostics."""
    return normalize_route_path(path)


def _should_redact_key(key: str) -> bool:
    return key.lower() in DIAGNOSTIC_REDACT_KEYS


def _redact_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _should_redact_key(str(key)) else _redact_data(val)
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_redact_data(item) for item in value]
    return value


def _to_json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _truncate_bytes(raw: bytes, max_bytes: int) -> tuple[str, bool]:
    if len(raw) <= max_bytes:
        return raw.decode("utf-8", errors="replace"), False

    truncated = raw[:max_bytes]
    return truncated.decode("utf-8", errors="replace"), True


def _truncate_text(text: str, max_bytes: int) -> tuple[str, bool]:
    return _truncate_bytes(text.encode("utf-8"), max_bytes)


def serialize_diagnostic_headers(headers: Mapping[str, str]) -> str:
    filtered: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered not in DIAGNOSTIC_HEADER_ALLOWLIST:
            continue
        filtered[lowered] = "[REDACTED]" if _should_redact_key(lowered) else value
    return _to_json_text(filtered)


def serialize_query_params(raw_query_string: bytes) -> str:
    parsed = parse_qs(raw_query_string.decode("utf-8", errors="replace"), keep_blank_values=True)
    normalized: dict[str, Any] = {}
    for key, values in parsed.items():
        normalized[key] = values[0] if len(values) == 1 else values
    return _to_json_text(_redact_data(normalized))


def summarize_request_body(
    body_bytes: bytes,
    content_type: str,
    request_size: int,
) -> tuple[str, bool]:
    lowered = (content_type or "").lower()
    if not body_bytes:
        return "", False

    if "multipart/form-data" in lowered:
        payload = {
            "summary": "multipart form-data omitted",
            "content_type": content_type,
            "request_size": request_size,
        }
        return _to_json_text(payload), False

    if "application/octet-stream" in lowered:
        payload = {
            "summary": "binary body omitted",
            "content_type": content_type,
            "request_size": request_size,
        }
        return _to_json_text(payload), False

    if "application/json" in lowered:
        try:
            parsed = json.loads(body_bytes.decode("utf-8", errors="replace"))
            sanitized = _to_json_text(_redact_data(parsed))
        except Exception:
            sanitized = body_bytes.decode("utf-8", errors="replace")
        return _truncate_text(sanitized, MAX_DIAGNOSTIC_BODY_BYTES)

    if "application/x-www-form-urlencoded" in lowered:
        parsed = parse_qs(body_bytes.decode("utf-8", errors="replace"), keep_blank_values=True)
        normalized: dict[str, Any] = {}
        for key, values in parsed.items():
            normalized[key] = values[0] if len(values) == 1 else values
        return _truncate_text(_to_json_text(_redact_data(normalized)), MAX_DIAGNOSTIC_BODY_BYTES)

    if lowered.startswith("text/") or "xml" in lowered or "javascript" in lowered:
        return _truncate_bytes(body_bytes, MAX_DIAGNOSTIC_BODY_BYTES)

    payload = {
        "summary": "non-text body omitted",
        "content_type": content_type,
        "request_size": request_size,
    }
    return _to_json_text(payload), False


def summarize_response_preview(body_bytes: bytes, content_type: str) -> str:
    lowered = (content_type or "").lower()
    if not body_bytes:
        return ""
    if "application/json" not in lowered and not lowered.startswith("text/") and "xml" not in lowered:
        return ""
    preview, _ = _truncate_bytes(body_bytes, MAX_DIAGNOSTIC_RESPONSE_PREVIEW_BYTES)
    return preview


def summarize_stack_trace(stack_trace: str) -> str:
    if not stack_trace:
        return ""
    truncated, _ = _truncate_text(stack_trace, MAX_DIAGNOSTIC_STACK_BYTES)
    return truncated
