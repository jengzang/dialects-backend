# User Suggestions Context Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revise user suggestions so category is open text, admin identity fields are removed, and each submission stores a recent API snapshot from `auth.db`.

**Architecture:** Keep the existing `user_suggestions` API paths. Extend the submit service to accept an auth database session for `ApiUsageLog` lookup, serialize a compact `recent_api` JSON array into `supplements.db`, and keep admin triage focused on status, priority, note, and handled time only.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic v2, SQLite, pytest.

---

## File Structure

- Modify `docs/superpowers/specs/2026-07-30-user-suggestions-design.md`: record the revised field decisions.
- Modify `tests/test_user_suggestions.py`: add red tests for open category, recent API snapshots, migration columns, and removed handler identity fields.
- Modify `app/service/user/core/models.py`: remove handler identity columns and add `recent_api`.
- Modify `app/service/user/core/database.py`: update create SQL and add idempotent `recent_api` migration for existing tables.
- Modify `app/schemas/user/suggestions.py`: make category open text, expose `recent_api`, and remove handler identity fields.
- Modify `app/service/user/suggestion.py`: remove category whitelist and build recent API snapshots.
- Modify `app/service/admin/suggestions.py`: remove admin identity handling.
- Modify `app/routes/user/suggestions.py`: inject the auth database session into submit handling.
- Modify `docs/superpowers/plans/2026-08-01-user-suggestions-context-revision.md`: track this implementation.

### Task 1: Tests

**Files:**
- Modify: `tests/test_user_suggestions.py`

- [x] **Step 1: Write failing tests**

Add tests for these behaviors:

- A custom category such as `performance_idea` is accepted and stored.
- Logged-in submission stores up to 10 `recent_api` entries, taking user-id rows first and then filling remaining slots with IP rows.
- Anonymous submission stores IP-based `recent_api` entries.
- `recent_api` entries include `name`, `time`, and `duration`, and do not include `status_code`.
- Admin terminal status update sets `handled_at` but no longer returns `handled_by` or `handled_by_username`.
- Migration creates `recent_api` and does not create handler identity columns for fresh tables.

- [x] **Step 2: Verify tests fail before implementation**

Run:

```bash
.venv/bin/python -m pytest tests/test_user_suggestions.py -q
```

Expected: failure from current category whitelist, missing recent API behavior, and old handler fields.

### Task 2: Model, Migration, and Schemas

**Files:**
- Modify: `app/service/user/core/models.py`
- Modify: `app/service/user/core/database.py`
- Modify: `app/schemas/user/suggestions.py`

- [x] **Step 1: Update ORM model**

Add `recent_api = Column(Text, nullable=True)` and remove `handled_by` and
`handled_by_username`.

- [x] **Step 2: Update migration SQL**

Fresh table SQL includes `recent_api` and excludes handler identity columns.
Existing tables get `ALTER TABLE user_suggestions ADD COLUMN recent_api TEXT`
when missing.

- [x] **Step 3: Update Pydantic schemas**

Use `category: str = Field("general", min_length=1, max_length=50)` instead of
literal categories. Add `recent_api: list[dict[str, Any]] = []` to item output.
Remove handler identity fields from item output.

### Task 3: Recent API Service Logic

**Files:**
- Modify: `app/service/user/suggestion.py`
- Modify: `app/routes/user/suggestions.py`
- Modify: `app/service/admin/suggestions.py`

- [x] **Step 1: Build recent API snapshot helper**

Query `ApiUsageLog` by user id first, newest first. Fill with IP rows if fewer
than 10 entries exist. Serialize each row as:

```python
{"name": row.path, "time": row.called_at.isoformat(), "duration": row.duration}
```

- [x] **Step 2: Store snapshot on create**

`create_suggestion()` accepts `auth_db` and stores JSON text in `recent_api`.
If lookup fails, store `[]` and continue.

- [x] **Step 3: Route dependency wiring**

`POST /api/suggestions` injects `app.service.auth.database.connection.get_db` as
the auth database dependency and passes it into the service.

- [x] **Step 4: Admin update cleanup**

Remove `mark_terminal_handler()` usage and set only `handled_at` for terminal
statuses.

### Task 4: Verification and Commit

- [x] **Step 1: Run focused tests**

```bash
.venv/bin/python -m pytest tests/test_user_suggestions.py -q
```

Expected: all suggestion tests pass.

- [x] **Step 2: Run adjacent tests**

```bash
.venv/bin/python -m pytest tests/test_user_custom_read_apis.py tests/test_user_custom_delete.py -q
```

Expected: all adjacent supplements tests pass.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-07-30-user-suggestions-design.md docs/superpowers/plans/2026-08-01-user-suggestions-context-revision.md tests/test_user_suggestions.py app/service/user/core/models.py app/service/user/core/database.py app/schemas/user/suggestions.py app/service/user/suggestion.py app/service/admin/suggestions.py app/routes/user/suggestions.py
git commit -m "feat: snapshot recent api for suggestions"
```
