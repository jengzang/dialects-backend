# OpenAPI Smoke Tests

This folder is for large-scale API smoke testing (for 200+ endpoints) and shared runtime config.

## Files

- `api_test_config.template.json`: template config
- `api_test_config.local.json`: local config (not committed)
- `openapi_smoke.py`: OpenAPI-driven smoke runner
- `reports/`: generated reports

## Setup

1. Copy config template:

   `StressTest/smoke/api_test_config.template.json`

   to:

   `StressTest/smoke/api_test_config.local.json`

2. Configure credentials:

- Recommended: keep `auth.password` empty
- Set environment variable from `auth.password_env` (default: `TEST_ADMIN_PASSWORD`)

3. Start backend locally (for example):

   `python run.py -r EXE -close`

## Run smoke tests

Run full smoke:

`python StressTest/smoke/openapi_smoke.py`

Run cluster loader smoke and benchmark:

`./.venv/bin/python StressTest/smoke/cluster_loader_smoke.py`

Run only first 30 endpoints:

`python StressTest/smoke/openapi_smoke.py --max-endpoints 30`

Use custom config path:

`python StressTest/smoke/openapi_smoke.py --config path/to/your.json`

## Notes

- This smoke runner focuses on endpoint availability, auth behavior, and basic request validity.
- It does not replace strict business-logic tests for critical endpoints.
- `cluster_loader_smoke.py` is a targeted cluster regression script. It checks loader equivalence, compares SQL plans for different query shapes, benchmarks them, and runs a minimal cluster smoke across the three `phoneme_mode` values.
