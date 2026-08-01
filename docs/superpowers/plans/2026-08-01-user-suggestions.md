# User Suggestions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add anonymous-or-authenticated user suggestion storage in `supplements.db`, plus user and admin APIs.

**Architecture:** Keep the feature in the existing supplements ORM stack. Add one `UserSuggestion` SQLAlchemy model, one startup migration function, focused service modules for user/admin behavior, Pydantic schemas, and FastAPI routers registered under `/api/suggestions` and `/admin/suggestions`.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic v2, SQLite, pytest/unittest.

---

## File Structure

- Create `tests/test_user_suggestions.py`: route, service, and migration coverage for the new behavior.
- Modify `app/service/user/core/models.py`: add the `UserSuggestion` ORM model.
- Modify `app/service/user/core/database.py`: add idempotent table/index migration.
- Modify `app/lifecycle/startup.py`: run the new supplements migration at startup.
- Create `app/schemas/user/suggestions.py`: request/response models and enum-like validation.
- Modify `app/schemas/user/__init__.py`: export suggestion schemas.
- Create `app/service/user/suggestion.py`: create and list-own suggestion behavior.
- Create `app/service/admin/suggestions.py`: admin list and update behavior.
- Create `app/routes/user/suggestions.py`: user-facing API routes.
- Create `app/routes/admin/suggestions.py`: admin API routes.
- Modify `app/routes/__init__.py`: register user-facing router under `/api`.
- Modify `app/routes/admin/__init__.py`: register admin router under `/admin/suggestions`.

### Task 1: Tests

**Files:**
- Create: `tests/test_user_suggestions.py`

- [x] **Step 1: Write failing tests**

Add tests that import the desired modules and call the desired APIs. The test
file covers these behaviors:

- `test_anonymous_submit_stores_no_user_identity`
- `test_authenticated_submit_stores_user_identity`
- `test_invalid_category_is_rejected_by_schema`
- `test_my_suggestions_requires_login`
- `test_my_suggestions_only_returns_current_user_rows`
- `test_admin_list_filters_by_status_and_category`
- `test_admin_update_sets_handler_fields_for_terminal_status`
- `test_migration_creates_user_suggestions_table_idempotently`

- [x] **Step 2: Verify tests fail for missing feature**

Run:

```bash
python3 -m pytest tests/test_user_suggestions.py -q
```

Expected: fail during import because suggestion modules do not exist yet.

### Task 2: ORM and Migration

**Files:**
- Modify: `app/service/user/core/models.py`
- Modify: `app/service/user/core/database.py`
- Modify: `app/lifecycle/startup.py`

- [x] **Step 1: Add `UserSuggestion` model**

Fields match the approved design: nullable identity, title/content/category,
source/context/contact, submitter metadata, status/priority/admin handling, and
timestamps.

- [x] **Step 2: Add `migrate_user_suggestions_table()`**

Use `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` through the
existing `engine.connect()` pattern.

- [x] **Step 3: Call migration at startup**

Update the existing supplements schema check to call both
`migrate_user_regions_table()` and `migrate_user_suggestions_table()`.

### Task 3: Schemas and Services

**Files:**
- Create: `app/schemas/user/suggestions.py`
- Modify: `app/schemas/user/__init__.py`
- Create: `app/service/user/suggestion.py`
- Create: `app/service/admin/suggestions.py`

- [x] **Step 1: Add schemas**

Define create, item, list, and admin update schemas. Validate categories,
statuses, priorities, and trimmed text lengths.

- [x] **Step 2: Add user service**

Implement creation with optional logged-in user fields, JSON serialization of
context, IP/user-agent capture, rollback on error, and own-list pagination.

- [x] **Step 3: Add admin service**

Implement filterable listing and update. Terminal statuses set handler fields.

### Task 4: Routes and Registration

**Files:**
- Create: `app/routes/user/suggestions.py`
- Create: `app/routes/admin/suggestions.py`
- Modify: `app/routes/__init__.py`
- Modify: `app/routes/admin/__init__.py`

- [x] **Step 1: Add user routes**

`POST /api/suggestions` accepts anonymous users, while
`GET /api/suggestions/my` requires login.

- [x] **Step 2: Add admin routes**

`GET /admin/suggestions` lists suggestions and
`PATCH /admin/suggestions/{suggestion_id}` updates triage state.

- [x] **Step 3: Register routes**

Include the user router under `/api` and the admin router under
`/admin/suggestions`.

### Task 5: Verification and Commit

- [x] **Step 1: Run targeted tests**

```bash
python3 -m pytest tests/test_user_suggestions.py -q
```

Expected: all tests pass.

- [x] **Step 2: Run relevant existing tests**

```bash
python3 -m pytest tests/test_user_custom_read_apis.py tests/test_user_custom_delete.py -q
```

Expected: all tests pass.

- [x] **Step 3: Review diff and status**

```bash
git diff --stat
git status --short
```

Expected: only suggestion feature files are staged for commit; unrelated local
changes remain unstaged.

- [ ] **Step 4: Commit**

```bash
git add app/service/user/core/models.py app/service/user/core/database.py app/lifecycle/startup.py app/schemas/user/suggestions.py app/schemas/user/__init__.py app/service/user/suggestion.py app/service/admin/suggestions.py app/routes/user/suggestions.py app/routes/admin/suggestions.py app/routes/__init__.py app/routes/admin/__init__.py tests/test_user_suggestions.py docs/superpowers/plans/2026-08-01-user-suggestions.md
git commit -m "feat: add user suggestions api"
```
