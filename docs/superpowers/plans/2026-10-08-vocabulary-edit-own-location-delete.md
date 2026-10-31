# Vocabulary `edit` Self-Location Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permit `edit` users to delete one of their own vocabulary locations and its entries, without granting any cross-user deletion or location-transfer privilege.

**Architecture:** Keep FastAPI as the sole authorization authority. `/api/vocabulary/me` exposes an explicit deletion capability for UI gating; `DELETE /locations/{location_name}` independently scopes every `edit` request to `current_user.id` before counting or deleting data. The existing single transaction continues to delete matching entries, the location row, and record an audit log together.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy, SQLite, pytest.

---

## Scope Lock

- Grant only the existing `edit` role. Do not broaden `one`, `two`, or `three`; those quota-limited roles remain unable to delete an entire location.
- Keep `manage`/admin cross-user deletion and duplicate-name ambiguity behavior exactly as it is, including `user_id` disambiguation.
- Keep transfer restricted to `manage`.
- Do not add migrations, tables, a deletion-preview endpoint, background work, or a route path.

## File Map

| File | Change |
| --- | --- |
| `app/schemas/vocabulary.py` | Add the typed `can_delete_locations` field to `VocabularyMeResponse`. |
| `app/routes/vocabulary.py` | Return the capability and change only delete-route target scoping. |
| `tests/test_vocabulary_routes.py` | Add route, capability, ownership, cascade, and ambiguity regression tests. |
| `docs/api/vocabulary_frontend_backend_gap_analysis.md` | Update the published authorization contract. |

### Task 1: Capture the deletion authorization boundaries in route tests

**Files:**
- Modify: `tests/test_vocabulary_routes.py:14-31,330-350,600-645,1493-1535`

- [ ] **Step 1: Make the delete endpoint part of the private-route dependency test**

  Import `delete_vocabulary_location` and extend the existing dependency loop:

  ```python
  from app.routes.vocabulary import (
      delete_vocabulary_location,
      # existing endpoint imports
  )

  def test_locations_endpoints_depend_on_current_user() -> None:
      for endpoint in (
          get_vocabulary_locations,
          update_vocabulary_location,
          delete_vocabulary_location,
      ):
          dependency = signature(endpoint).parameters["current_user"].default.dependency
          assert dependency is get_current_user
  ```

- [ ] **Step 2: Write the failing owner-cascade test for `edit`**

  Seed an `edit` permission for user 7, a user-7 `息烽` location with two entries, a user-7 `保留地`, and user 8's same-named location with one entry. Call delete as user 7 without a `user_id` and assert the exact response, user 7's target rows removed, user 8's same-name rows retained, and one accurate audit record.

  ```python
  result = delete_vocabulary_location(
      location_name="息烽",
      user_id=None,
      current_user=_User(7),
      db=session,
  )

  assert result == {
      "status": "deleted",
      "location_name": "息烽",
      "deleted_entries": 2,
  }
  assert session.query(VocabularyLocation).filter_by(user_id=7, location_name="息烽").count() == 0
  assert session.query(VocabularyEntry).filter_by(user_id=7, location_name="息烽").count() == 0
  assert session.query(VocabularyLocation).filter_by(user_id=8, location_name="息烽").count() == 1
  assert session.query(VocabularyEntry).filter_by(user_id=8, location_name="息烽").count() == 1
  ```

- [ ] **Step 3: Run the test before implementation**

  ```bash
  python -m pytest -q tests/test_vocabulary_routes.py -k 'edit_user_can_delete_own_location'
  ```

  Expected before implementation: failure with HTTP 403 and `仅 manage/admin 可删除地点`.

- [ ] **Step 4: Add cross-owner and quota-tier denial tests**

  Assert that user 7 with `edit` receives 403 and creates no log when sending `user_id=8`, even if the target name exists. In a separate test, seed `permission_level="one"` for the owner and assert own-location deletion remains 403 with both location and entry intact. Use this common assertion pattern:

  ```python
  with pytest.raises(HTTPException) as raised:
      delete_vocabulary_location(
          location_name="息烽",
          user_id=8,
          current_user=_User(7),
          db=session,
      )

  assert raised.value.status_code == 403
  assert session.query(VocabularyLog).count() == 0
  ```

- [ ] **Step 5: Add manage duplicate-name targeting coverage**

  Seed user 7 and 8 with locations/entries both named `息烽`; grant user 9 `manage`; delete with `user_id=8`. Assert only user 8's location and entry are removed and the audit log targets `user_id = 8`. This fixes coverage for the already-supported disambiguation query parameter.

### Task 2: Add the `/me` capability and owner-scoped delete implementation

**Files:**
- Modify: `app/schemas/vocabulary.py:259-265`
- Modify: `app/routes/vocabulary.py:537-596,801-825`
- Test: `tests/test_vocabulary_routes.py`

- [ ] **Step 1: Extend the Pydantic response model**

  ```python
  class VocabularyMeResponse(BaseModel):
      user_id: int
      permission_level: str | None
      can_upload: bool
      can_manage_entries: bool
      can_view_logs: bool
      can_delete_locations: bool
  ```

- [ ] **Step 2: Populate the field in every `/me` response branch**

  Keep admin mapped to `manage`; both it and an ordinary `manage` user return `True`. Only direct `edit` returns `True` among non-manage permission levels:

  ```python
  # admin response
  can_delete_locations=True,

  # regular response
  can_delete_locations=permission_level in {"edit", "manage"},
  ```

  Extend `test_my_permission_endpoint_returns_effective_permission_or_null` to assert `True` for edit and admin, `False` for no permission and `one`.

- [ ] **Step 3: Scope the delete query before target lookup**

  Replace only the initial role guard/query construction. Retain the current not-found, ambiguity, count, cascade, log, commit, and rollback code unchanged.

  ```python
  query = db.query(VocabularyLocation).filter(
      VocabularyLocation.location_name == location_name,
  )

  if permission_level == "edit":
      if user_id is not None and user_id != current_user.id:
          raise HTTPException(status_code=403, detail="只能删除自己的地点")
      query = query.filter(VocabularyLocation.user_id == current_user.id)
  elif permission_level == "manage":
      if user_id is not None:
          query = query.filter(VocabularyLocation.user_id == user_id)
  else:
      raise HTTPException(status_code=403, detail="仅 edit/manage 可删除地点")
  ```

  Do not rely on `can_delete_locations` from a request body or query parameter: it is only a server-generated UI hint.

- [ ] **Step 4: Run the focused route suite**

  ```bash
  python -m pytest -q tests/test_vocabulary_routes.py
  ```

  Expected: all tests pass. If the active shell lacks pytest, use the repository's normal virtual environment or dependency bootstrap rather than weakening the test set or route checks.

- [ ] **Step 5: Code-review and commit the backend unit**

  ```bash
  git diff --check
  git diff -- app/schemas/vocabulary.py app/routes/vocabulary.py tests/test_vocabulary_routes.py
  git add app/schemas/vocabulary.py app/routes/vocabulary.py tests/test_vocabulary_routes.py
  git commit -m "feat: allow edit users to delete own vocabulary locations"
  ```

### Task 3: Publish the updated frontend contract

**Files:**
- Modify: `docs/api/vocabulary_frontend_backend_gap_analysis.md:1579-1596`

- [ ] **Step 1: Replace the obsolete “no location-level endpoint for edit” claim**

  Preserve the existing single-entry/batch-entry restrictions, then document these exact invariants:

  ```markdown
  - `edit` 用户可以删除自己名下的一个地点；该操作会级联删除该地点名下的全部 entries。
  - `edit` 用户通过 `user_id` 指向其他用户时返回 403。
  - `manage`/admin 可以删除任意地点；同名地点必须带 `user_id` 消歧。
  - `one`、`two`、`three` 当前仍不具备地点删除能力。
  ```

- [ ] **Step 2: Add the UI handoff rule**

  Specify that clients display deletion based on `/api/vocabulary/me.can_delete_locations`, display transfer from their manage-only capability, and always forward the selected location's `user_id` to the delete endpoint.

- [ ] **Step 3: Review and commit this documentation-only change**

  ```bash
  git diff --check
  git diff -- docs/api/vocabulary_frontend_backend_gap_analysis.md
  git add docs/api/vocabulary_frontend_backend_gap_analysis.md
  git commit -m "docs: clarify vocabulary location delete permissions"
  ```

## Verification Checklist

- [ ] Anonymous callers remain rejected by the route dependency.
- [ ] `edit` can delete only the caller's location and matching entries.
- [ ] Forged ownership and `one`-tier requests are 403 with no mutation/log.
- [ ] `manage` duplicate-name deletion mutates only the explicitly selected owner.
- [ ] Successful deletion remains atomic and logs `location + entry-count` affected rows.
- [ ] `GET /api/vocabulary/me` supplies the capability for every permission branch.
