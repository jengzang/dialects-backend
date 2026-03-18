from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE_CONFIG = SCRIPT_DIR / "api_test_config.template.json"
DEFAULT_LOCAL_CONFIG = SCRIPT_DIR / "api_test_config.local.json"
DEFAULT_REPORT_DIR = SCRIPT_DIR / "reports"
PATH_PARAM_PATTERN = re.compile(r"{([^{}]+)}")
SUPPORTED_HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def _select_config_path(cli_path: Optional[str]) -> Path:
    if cli_path:
        return Path(cli_path)

    env_path = os.getenv("SMOKE_API_CONFIG") or os.getenv("TEST_API_CONFIG")
    if env_path:
        return Path(env_path)

    if DEFAULT_LOCAL_CONFIG.exists():
        return DEFAULT_LOCAL_CONFIG

    return DEFAULT_TEMPLATE_CONFIG


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _resolve_ref(spec: Dict[str, Any], ref: str) -> Dict[str, Any]:
    if not ref.startswith("#/"):
        return {}
    node: Any = spec
    for part in ref[2:].split("/"):
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return {}
        if node is None:
            return {}
    return node if isinstance(node, dict) else {}


def _resolved_object(spec: Dict[str, Any], obj: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        return {}
    if "$ref" in obj:
        return _resolved_object(spec, _resolve_ref(spec, obj["$ref"]))
    return obj


def _merge_schemas(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if key == "properties":
            merged.setdefault("properties", {})
            if isinstance(value, dict):
                merged["properties"].update(value)
        elif key == "required":
            req = set(merged.get("required", []))
            if isinstance(value, list):
                req.update(value)
            merged["required"] = sorted(req)
        else:
            merged[key] = value
    return merged


def _resolve_schema(spec: Dict[str, Any], schema: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    if depth > 8 or not isinstance(schema, dict):
        return {}

    schema = _resolved_object(spec, schema)

    if "allOf" in schema and isinstance(schema["allOf"], list):
        merged: Dict[str, Any] = {}
        for part in schema["allOf"]:
            merged = _merge_schemas(merged, _resolve_schema(spec, part, depth + 1))
        schema = _merge_schemas(schema, merged)

    if "oneOf" in schema and isinstance(schema["oneOf"], list) and schema["oneOf"]:
        picked = _resolve_schema(spec, schema["oneOf"][0], depth + 1)
        schema = _merge_schemas(schema, picked)

    if "anyOf" in schema and isinstance(schema["anyOf"], list) and schema["anyOf"]:
        picked = _resolve_schema(spec, schema["anyOf"][0], depth + 1)
        schema = _merge_schemas(schema, picked)

    return schema


def _sample_scalar(schema: Dict[str, Any]) -> Any:
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]

    schema_type = schema.get("type")
    schema_format = schema.get("format")

    if schema_type == "integer":
        minimum = schema.get("minimum", 1)
        return int(minimum) if isinstance(minimum, (int, float)) else 1
    if schema_type == "number":
        minimum = schema.get("minimum", 1.0)
        return float(minimum) if isinstance(minimum, (int, float)) else 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "string":
        if schema_format == "date-time":
            return "2026-01-01T00:00:00Z"
        if schema_format == "date":
            return "2026-01-01"
        if schema_format == "email":
            return "smoke-test@example.com"
        if schema_format == "uuid":
            return "11111111-1111-1111-1111-111111111111"
        if schema_format in {"uri", "url"}:
            return "https://example.com"
        min_len = schema.get("minLength", 1)
        text = "test"
        if isinstance(min_len, int) and min_len > len(text):
            text = "t" * min_len
        return text

    return None


def _sample_from_schema(spec: Dict[str, Any], schema: Dict[str, Any], depth: int = 0) -> Any:
    if depth > 8 or not isinstance(schema, dict):
        return None

    schema = _resolve_schema(spec, schema, depth)
    scalar = _sample_scalar(schema)
    if scalar is not None:
        return scalar

    schema_type = schema.get("type")
    if not schema_type:
        if "properties" in schema:
            schema_type = "object"
        elif "items" in schema:
            schema_type = "array"

    if schema_type == "object":
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        result: Dict[str, Any] = {}
        if isinstance(props, dict):
            for key, prop_schema in props.items():
                include = key in required
                if not include and isinstance(prop_schema, dict):
                    include = any(k in prop_schema for k in ("default", "example", "enum"))
                if not include:
                    continue
                sampled = _sample_from_schema(spec, prop_schema, depth + 1)
                if sampled is not None:
                    result[key] = sampled
        return result

    if schema_type == "array":
        items_schema = schema.get("items", {})
        sampled = _sample_from_schema(spec, items_schema, depth + 1)
        if sampled is None:
            return []
        return [sampled]

    return {}


def _combine_parameters(path_item: Dict[str, Any], operation: Dict[str, Any]) -> List[Dict[str, Any]]:
    combined: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    for source in (path_item.get("parameters", []), operation.get("parameters", [])):
        if not isinstance(source, list):
            continue
        for param in source:
            if not isinstance(param, dict):
                continue
            key = (str(param.get("name", "")), str(param.get("in", "")))
            if key in seen:
                continue
            seen.add(key)
            combined.append(param)
    return combined


def _path_param_value(
    name: str,
    schema: Dict[str, Any],
    defaults: Dict[str, Any],
) -> Any:
    if name in defaults:
        return defaults[name]
    if name.lower().endswith("id") or name.lower() == "id":
        return 1
    sampled = _sample_scalar(schema)
    if sampled is not None:
        return sampled
    return "test"


def _build_path(
    raw_path: str,
    path_params: Dict[str, Any],
) -> str:
    built = raw_path
    for key, value in path_params.items():
        built = built.replace("{" + key + "}", str(value))
    return built


def _matches_prefix(path: str, prefixes: List[str]) -> bool:
    if not prefixes:
        return True
    return any(path.startswith(prefix) for prefix in prefixes)


def _collect_operations(spec: Dict[str, Any], smoke_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    include_prefixes = smoke_cfg.get("include_path_prefixes", [])
    exclude_prefixes = smoke_cfg.get("exclude_path_prefixes", [])
    exclude_paths = set(smoke_cfg.get("exclude_paths", []))
    methods = [m.lower() for m in smoke_cfg.get("methods", list(SUPPORTED_HTTP_METHODS))]

    operations: List[Dict[str, Any]] = []
    paths = spec.get("paths", {})
    for path, path_item in sorted(paths.items(), key=lambda x: x[0]):
        if not isinstance(path_item, dict):
            continue
        if path in exclude_paths:
            continue
        if exclude_prefixes and _matches_prefix(path, exclude_prefixes):
            continue
        if not _matches_prefix(path, include_prefixes):
            continue

        for method in methods:
            if method not in path_item:
                continue
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operations.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "path_item": path_item,
                    "operation": operation,
                }
            )

    return operations


def _auth_token(
    config: Dict[str, Any],
    base_url: str,
    timeout_seconds: float,
) -> Optional[str]:
    auth_cfg = config.get("auth", {})
    if not auth_cfg.get("enabled", True):
        return None

    username = os.getenv("TEST_ADMIN_USERNAME", auth_cfg.get("username", "admin"))
    password = ""
    password_env = auth_cfg.get("password_env", "")
    if password_env:
        password = os.getenv(password_env, "")
    if not password:
        password = os.getenv("TEST_ADMIN_PASSWORD", auth_cfg.get("password", ""))
    if not password:
        return None

    login_path = auth_cfg.get("login_path", "/auth/login")
    login_url = f"{base_url.rstrip('/')}{login_path}"
    response = requests.post(
        login_url,
        json={"username": username, "password": password},
        timeout=timeout_seconds,
    )
    if response.status_code != 200:
        return None

    payload = response.json()
    token = payload.get("access_token")
    return token if isinstance(token, str) and token else None


def _prepare_request(
    spec: Dict[str, Any],
    op: Dict[str, Any],
    smoke_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    path_item = op["path_item"]
    operation = op["operation"]
    raw_path = op["path"]

    params = _combine_parameters(path_item, operation)
    path_defaults = smoke_cfg.get("path_param_defaults", {})
    path_values: Dict[str, Any] = {}
    query_params: Dict[str, Any] = {}

    for param in params:
        param = _resolved_object(spec, param)
        name = str(param.get("name", "")).strip()
        location = str(param.get("in", "")).strip()
        if not name or not location:
            continue

        schema = _resolve_schema(spec, param.get("schema", {}))
        required = bool(param.get("required", False))
        sampled = _sample_from_schema(spec, schema)

        if location == "path":
            path_values[name] = _path_param_value(name, schema, path_defaults)
        elif location == "query":
            should_include = required or any(k in schema for k in ("default", "example", "enum"))
            if should_include:
                if sampled is None:
                    sampled = _sample_scalar(schema)
                if sampled is None:
                    sampled = "test"
                query_params[name] = sampled

    request_json = None
    request_data = None
    media_type = None
    request_body = _resolved_object(spec, operation.get("requestBody", {}))
    if request_body:
        content = request_body.get("content", {})
        if isinstance(content, dict) and content:
            if "application/json" in content:
                media_type = "application/json"
            elif "application/x-www-form-urlencoded" in content:
                media_type = "application/x-www-form-urlencoded"
            elif "multipart/form-data" in content:
                media_type = "multipart/form-data"
            else:
                media_type = next(iter(content.keys()))

            media_schema = content.get(media_type, {}).get("schema", {})
            sampled_body = _sample_from_schema(spec, media_schema)

            if media_type == "application/json":
                request_json = sampled_body if sampled_body is not None else {}
            elif media_type in {"application/x-www-form-urlencoded", "multipart/form-data"}:
                if isinstance(sampled_body, dict):
                    request_data = sampled_body
                else:
                    request_data = {}

    resolved_path = _build_path(raw_path, path_values)
    return {
        "path": resolved_path,
        "query": query_params,
        "json": request_json,
        "data": request_data,
        "media_type": media_type,
    }


def _run_operation(
    base_url: str,
    timeout_seconds: float,
    accepted_statuses: List[int],
    headers: Dict[str, str],
    method: str,
    op: Dict[str, Any],
    prepared: Dict[str, Any],
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}{prepared['path']}"
    start = time.perf_counter()
    try:
        request_headers = dict(headers)
        if prepared["media_type"] == "application/x-www-form-urlencoded":
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        if prepared["media_type"] == "multipart/form-data":
            # requests will set multipart boundary automatically when files are used.
            # Here we only send simple form fields for smoke checks.
            request_headers.pop("Content-Type", None)

        response = requests.request(
            method=method,
            url=url,
            params=prepared["query"] or None,
            json=prepared["json"],
            data=prepared["data"],
            headers=request_headers,
            timeout=timeout_seconds,
        )
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = response.status_code
        ok = status_code in accepted_statuses
        return {
            "ok": ok,
            "status_code": status_code,
            "elapsed_ms": elapsed_ms,
            "url": url,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "ok": False,
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "url": url,
            "error": str(exc),
        }


def _write_report(report_path: Path, payload: Dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAPI-driven smoke tests")
    parser.add_argument("--config", help="Path to smoke config JSON")
    parser.add_argument("--max-endpoints", type=int, default=0, help="Limit number of endpoints")
    parser.add_argument("--report", help="Output report path (json)")
    parser.add_argument("--no-auth", action="store_true", help="Do not login before requests")
    args = parser.parse_args()

    config_path = _select_config_path(args.config)
    config = _load_json(config_path)

    server_cfg = config.get("server", {})
    smoke_cfg = config.get("smoke", {})

    base_url = os.getenv("TEST_BASE_URL", server_cfg.get("base_url", "http://localhost:5000")).rstrip("/")
    openapi_path = server_cfg.get("openapi_path", "/openapi.json")
    timeout_seconds = float(os.getenv("TEST_TIMEOUT_SECONDS", config.get("defaults", {}).get("timeout_seconds", 15)))
    accepted_statuses = list(smoke_cfg.get("accepted_statuses", [200, 201, 202, 204, 400, 401, 403, 404, 405, 409, 422]))
    fail_on_any_error = bool(smoke_cfg.get("fail_on_any_error", True))

    max_endpoints = args.max_endpoints if args.max_endpoints > 0 else int(smoke_cfg.get("max_endpoints", 0))

    headers: Dict[str, str] = {"Accept": "application/json"}
    if not args.no_auth:
        token = _auth_token(config, base_url, timeout_seconds)
        if token:
            headers["Authorization"] = f"Bearer {token}"

    openapi_url = f"{base_url}{openapi_path}"
    try:
        openapi_resp = requests.get(openapi_url, timeout=timeout_seconds)
        openapi_resp.raise_for_status()
        spec = openapi_resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to fetch OpenAPI spec from {openapi_url}: {exc}")
        return 2

    operations = _collect_operations(spec, smoke_cfg)
    if max_endpoints > 0:
        operations = operations[:max_endpoints]

    print(f"[INFO] Config: {config_path}")
    print(f"[INFO] Base URL: {base_url}")
    print(f"[INFO] OpenAPI: {openapi_url}")
    print(f"[INFO] Endpoints selected: {len(operations)}")

    results: List[Dict[str, Any]] = []
    for idx, op in enumerate(operations, start=1):
        method = op["method"]
        prepared = _prepare_request(spec, op, smoke_cfg)
        result = _run_operation(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            accepted_statuses=accepted_statuses,
            headers=headers,
            method=method,
            op=op,
            prepared=prepared,
        )
        item = {
            "index": idx,
            "method": method,
            "path": op["path"],
            "resolved_path": prepared["path"],
            "status_code": result["status_code"],
            "elapsed_ms": result["elapsed_ms"],
            "ok": result["ok"],
            "url": result["url"],
            "error": result["error"],
        }
        results.append(item)
        status_text = item["status_code"] if item["status_code"] is not None else "EXC"
        mark = "PASS" if item["ok"] else "FAIL"
        print(f"[{mark}] {idx:03d} {method:<6} {prepared['path']:<60} status={status_text} time={item['elapsed_ms']}ms")

    total = len(results)
    passed = sum(1 for x in results if x["ok"])
    failed = total - passed
    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round((passed / total) * 100, 2) if total else 0.0,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(args.report) if args.report else (DEFAULT_REPORT_DIR / f"openapi_smoke_{timestamp}.json")
    report_payload = {
        "timestamp": datetime.now().isoformat(),
        "config_path": str(config_path),
        "base_url": base_url,
        "openapi_url": openapi_url,
        "accepted_statuses": accepted_statuses,
        "summary": summary,
        "results": results,
    }
    _write_report(report_path, report_payload)

    print(
        f"[SUMMARY] total={summary['total']} passed={summary['passed']} failed={summary['failed']} "
        f"pass_rate={summary['pass_rate']}% report={report_path}"
    )

    if fail_on_any_error and failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
