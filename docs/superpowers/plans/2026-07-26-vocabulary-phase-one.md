# Vocabulary Phase One Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the phase-one vocabulary backend with `vocabulary.db`, permission checks, location metadata storage, replacement import behavior, and vocabulary-scoped SQL editor APIs.

**Architecture:** Build a focused `app/service/vocabulary/` module with database, parser, permission, location normalization, upload service, and audit logging boundaries. Expose `/api/vocabulary/upload` plus `/api/vocabulary/sql/*` routes that operate only on `vocabulary.db` and enforce row-level `user_id` scope for `edit` users.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, pandas/openpyxl/xlrd, python-docx, pytest

---

## File Structure

- Create `app/service/vocabulary/models.py`: SQLAlchemy models for entries, locations, permissions.
- Create `app/service/vocabulary/database.py`: SQLite engine/session and `migrate_vocabulary_database()`.
- Create `app/service/vocabulary/parser.py`: table/doc parsers and row validation.
- Create `app/service/vocabulary/location.py`: frontend location JSON normalization.
- Create `app/service/vocabulary/permissions.py`: effective `edit`/`manage` permission lookup.
- Create `app/service/vocabulary/logging.py`: operation-level vocabulary edit audit log writer.
- Create `app/service/vocabulary/service.py`: transactional upload replacement workflow.
- Create `app/service/vocabulary/__init__.py`: package exports.
- Create `app/schemas/vocabulary.py`: response/request helper schemas.
- Create `app/schemas/vocabulary_sql.py`: vocabulary-only query/edit request schemas without `db_key`.
- Create `app/routes/vocabulary.py`: `/upload` API.
- Create `app/routes/vocabulary_sql.py`: `/api/vocabulary/sql/*` query/edit APIs with table policies and row-level scope.
- Modify `app/routes/__init__.py`: register router under `/api/vocabulary`.
- Modify `app/lifecycle/startup.py`: call vocabulary migration when `AUTO_MIGRATE` is enabled.
- Modify `app/common/path.py`: add `VOCABULARY_DB_PATH`, `VOCABULARY_DB_URL`, and `vocabulary` db mapping.
- Create `tests/test_vocabulary_parser.py`: parser and location normalization tests.
- Create `tests/test_vocabulary_service.py`: permissions and transactional replacement tests.
- Create `tests/test_vocabulary_routes.py`: route dependency/registration smoke tests.
- Create `tests/test_vocabulary_sql_routes.py`: row-level permission, logging, and route schema tests.

## Tasks

### Task 1: Add parser and location failing tests

- [ ] Write tests in `tests/test_vocabulary_parser.py` that assert:
  - `parse_vocabulary_file()` imports `tests/息烽.xlsx`.
  - `written` maps to `standard_word`.
  - Chinese/English column aliases normalize.
  - bracket text parser extracts `standard_word`, `local_expression`, `ipa`, `notes`.
  - `normalize_location_payload()` accepts `簡稱` and `經緯度` aliases.
- [ ] Run `pytest tests/test_vocabulary_parser.py -v`.
- [ ] Confirm failure is due to missing `app.service.vocabulary` modules.

### Task 2: Implement parser and location normalization

- [ ] Create `app/service/vocabulary/location.py`.
- [ ] Create `app/service/vocabulary/parser.py`.
- [ ] Implement table parsing for `.xlsx`, `.xls`, `.csv`, and `.tsv`.
- [ ] Implement docx paragraph extraction for whitespace and bracket modes.
- [ ] Support `.doc` with an explicit best-effort fallback: use `antiword` when available, macOS `textutil` when available, then plain-text decoding; return a clear conversion error if none can extract text.
- [ ] Run `pytest tests/test_vocabulary_parser.py -v`.

### Task 3: Add database, permission, and upload service failing tests

- [ ] Write tests in `tests/test_vocabulary_service.py` that assert:
  - admin users resolve to `manage`.
  - users with `permission_level="edit"` resolve to `edit`.
  - users without permission raise `403`.
  - upload replaces existing entries for the same `(user_id, location_name)` and keeps other users' rows.
  - upload upserts the location row.
- [ ] Run `pytest tests/test_vocabulary_service.py -v`.
- [ ] Confirm failure is due to missing database/service implementation.

### Task 4: Implement database, permissions, and service

- [ ] Add vocabulary path constants and `DB_MAPPING["vocabulary"]`.
- [ ] Create SQLAlchemy models and schema migration.
- [ ] Implement `get_effective_permission_level()`.
- [ ] Implement `import_vocabulary_upload()` with one transaction:
  - normalize location JSON.
  - parse file.
  - upsert location.
  - delete existing current user's entries for `location_name`.
  - insert parsed entries.
  - return import statistics.
- [ ] Run `pytest tests/test_vocabulary_service.py -v`.

### Task 5: Add route tests and route implementation

- [ ] Write `tests/test_vocabulary_routes.py` to assert:
  - the main app contains `/api/vocabulary/upload`.
  - the upload endpoint depends on `get_current_user`.
- [ ] Run `pytest tests/test_vocabulary_routes.py -v`.
- [ ] Create `app/routes/vocabulary.py`.
- [ ] Create `app/schemas/vocabulary.py`.
- [ ] Register router in `app/routes/__init__.py`.
- [ ] Add startup migration in `app/lifecycle/startup.py`.
- [ ] Run route tests again.

### Task 6: Focused verification

- [ ] Run `pytest tests/test_vocabulary_parser.py tests/test_vocabulary_service.py tests/test_vocabulary_routes.py -v`.
- [ ] Run `pytest tests/test_vocabulary_sql_routes.py -v`.
- [ ] Run nearby route import smoke tests if needed: `pytest tests/test_run_py_port_selection.py tests/test_sql_admin_permissions.py -v`.
- [ ] Inspect `git diff --stat` and `git diff --check`.
- [ ] Confirm no unrelated existing worktree changes were modified.

### Task 7: Add vocabulary SQL editor APIs

- [ ] Add `vocabulary_logs` to `app/service/vocabulary/models.py`.
- [ ] Include `operation_id`, `source`, and `status` in `vocabulary_logs` so logs are grouped by user operation instead of row-level changes.
- [ ] Remove unused `created_at` and `updated_at` columns from `vocabulary_entries`, `vocabulary_locations`, and `vocabulary_permissions`.
- [ ] Add migration logic in `app/service/vocabulary/database.py` that rebuilds existing vocabulary tables to the expected column set.
- [ ] Add `app/schemas/vocabulary_sql.py` schemas that deliberately omit `db_key`.
- [ ] Add `app/routes/vocabulary_sql.py` with:
  - query, column info, count, distinct, and distinct-query endpoints.
  - mutate and batch-mutate endpoints.
  - batch-replace-preview and batch-replace-execute endpoints.
  - fixed vocabulary DB access through `get_vocabulary_db`.
  - table whitelist: `vocabulary_entries`, `vocabulary_locations`, and manage-only read access to `vocabulary_logs`.
  - no `vocabulary_permissions` exposure through generic vocabulary SQL routes.
  - row-level `user_id = current_user.id` scope for `edit`.
  - shared batch replace where-builder for preview and execute.
- [ ] Register the router under `/api/vocabulary/sql`.
- [ ] Log upload and every SQL edit operation to `vocabulary_logs` as one row per user operation.
