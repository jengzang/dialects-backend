from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import pytest
import requests


TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent

STRESS_SMOKE_DIR = PROJECT_ROOT / "StressTest" / "smoke"
DEFAULT_TEMPLATE_CONFIG = STRESS_SMOKE_DIR / "api_test_config.template.json"
DEFAULT_LOCAL_CONFIG = STRESS_SMOKE_DIR / "api_test_config.local.json"

# Backward-compatible fallback (legacy location).
LEGACY_CONFIG_DIR = TEST_DIR / "config"
LEGACY_TEMPLATE_CONFIG = LEGACY_CONFIG_DIR / "api_test_config.template.json"
LEGACY_LOCAL_CONFIG = LEGACY_CONFIG_DIR / "api_test_config.local.json"


def _select_config_path() -> Path:
    env_path = os.getenv("TEST_API_CONFIG")
    if env_path:
        return Path(env_path)
    if DEFAULT_LOCAL_CONFIG.exists():
        return DEFAULT_LOCAL_CONFIG
    if DEFAULT_TEMPLATE_CONFIG.exists():
        return DEFAULT_TEMPLATE_CONFIG
    if LEGACY_LOCAL_CONFIG.exists():
        return LEGACY_LOCAL_CONFIG
    return LEGACY_TEMPLATE_CONFIG


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Test config not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture(scope="session")
def api_test_config() -> Dict[str, Any]:
    path = _select_config_path()
    data = _load_json(path)
    data["_config_path"] = str(path)
    return data


@pytest.fixture(scope="session")
def base_url(api_test_config: Dict[str, Any]) -> str:
    server_cfg = api_test_config.get("server", {})
    value = os.getenv("TEST_BASE_URL", server_cfg.get("base_url", "http://localhost:5000"))
    return value.rstrip("/")


@pytest.fixture(scope="session")
def request_timeout(api_test_config: Dict[str, Any]) -> float:
    env_timeout = os.getenv("TEST_TIMEOUT_SECONDS")
    if env_timeout:
        return float(env_timeout)
    defaults = api_test_config.get("defaults", {})
    return float(defaults.get("timeout_seconds", 15))


@pytest.fixture(scope="session")
def admin_username(api_test_config: Dict[str, Any]) -> str:
    auth_cfg = api_test_config.get("auth", {})
    return os.getenv("TEST_ADMIN_USERNAME", auth_cfg.get("username", "admin"))


@pytest.fixture(scope="session")
def admin_password(api_test_config: Dict[str, Any]) -> str:
    auth_cfg = api_test_config.get("auth", {})

    password_env_name = auth_cfg.get("password_env")
    if password_env_name:
        value = os.getenv(password_env_name, "")
        if value:
            return value

    value = os.getenv("TEST_ADMIN_PASSWORD", auth_cfg.get("password", ""))
    if value:
        return value

    config_path = api_test_config.get("_config_path", "<unknown>")
    pytest.skip(
        "Admin password is not configured. "
        f"Set TEST_ADMIN_PASSWORD (or the env in auth.password_env), config file: {config_path}"
    )


@pytest.fixture(scope="session")
def token(
    api_test_config: Dict[str, Any],
    base_url: str,
    request_timeout: float,
    admin_username: str,
    admin_password: str,
) -> str:
    auth_cfg = api_test_config.get("auth", {})
    login_path = auth_cfg.get("login_path", "/auth/login")
    login_url = f"{base_url}{login_path}"

    response = requests.post(
        login_url,
        json={"username": admin_username, "password": admin_password},
        timeout=request_timeout,
    )
    assert response.status_code == 200, f"Login failed: {response.status_code} {response.text}"

    payload = response.json()
    access_token = payload.get("access_token")
    assert access_token, f"Login response missing access_token: {payload}"
    return access_token


@pytest.fixture(scope="session")
def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def api_case(api_test_config: Dict[str, Any]):
    cases = api_test_config.get("cases", {})

    def _get(name: str) -> Dict[str, Any]:
        if name not in cases:
            raise KeyError(f"Case '{name}' not found in test config")
        return cases[name]

    return _get


@pytest.fixture(scope="session")
def api_path(
    api_test_config: Dict[str, Any],
    base_url: str,
    request_timeout: float,
    auth_headers: Dict[str, str],
) -> str:
    env_path = os.getenv("TEST_API_PATH", "").strip()
    if env_path:
        return env_path

    fixtures_cfg = api_test_config.get("fixtures", {})
    cfg_path = str(fixtures_cfg.get("api_path", "")).strip()
    if cfg_path:
        return cfg_path

    response = requests.get(
        f"{base_url}/admin/leaderboard/available-apis",
        headers=auth_headers,
        timeout=request_timeout,
    )
    if response.status_code == 200:
        apis = response.json().get("apis", [])
        if apis:
            return apis[0]

    pytest.skip(
        "Cannot resolve api_path. Set TEST_API_PATH or fixtures.api_path in config."
    )
