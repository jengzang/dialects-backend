# `/api/notes` Leaderboard Category Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Include the exact `/api/notes` endpoint in the user leaderboard category `category_字調查詢`.

**Architecture:** Keep the existing exact-path category rule mechanism unchanged. Add `/api/notes` to `CATEGORY_RULES["category_字調查詢"]["paths"]`, and protect the behavior with a focused test that inspects the generated SQL condition or the category rule directly.

**Tech Stack:** Python, pytest, SQLAlchemy query-builder helpers.

---

### Task 1: Add a regression test for the category path

**Files:**
- Test: `tests/test_leaderboard_service.py` (create if absent)

- [x] **Step 1: Write the failing test**

Add a test that imports `CATEGORY_RULES` and asserts the exact path is present in the category rule:

```python
from app.service.user.leaderboard_service import CATEGORY_RULES


def test_notes_endpoint_belongs_to_character_tone_category():
    assert "/api/notes" in CATEGORY_RULES["category_字調查詢"]["paths"]
```

- [x] **Step 2: Run the focused test and verify it fails**

Run:

```bash
pytest tests/test_leaderboard_service.py::test_notes_endpoint_belongs_to_character_tone_category -q
```

Expected: FAIL because `/api/notes` is not yet in the category's `paths` list.

### Task 2: Add the exact endpoint path

**Files:**
- Modify: `app/service/user/leaderboard_service.py` in the `category_字調查詢` `paths` list

- [x] **Step 1: Add the minimal implementation**

Add this exact path alongside the existing character/tone query paths:

```python
"/api/notes",
```

Do not add a `/api/notes/` prefix rule.

- [x] **Step 2: Run the focused regression test**

Run:

```bash
pytest tests/test_leaderboard_service.py::test_notes_endpoint_belongs_to_character_tone_category -q
```

Expected: PASS.

### Task 3: Verify surrounding leaderboard behavior

- [x] **Step 1: Run the complete leaderboard-focused test file**

Run:

```bash
pytest tests/test_leaderboard_service.py -q
```

Expected: all tests pass with no failures.

- [x] **Step 2: Review the final diff**

Run:

```bash
git diff --check
git diff -- app/service/user/leaderboard_service.py tests/test_leaderboard_service.py
```

Confirm the only behavior change is the exact `/api/notes` category membership plus its regression test.
