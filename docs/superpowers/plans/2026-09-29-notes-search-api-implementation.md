# Notes Search API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide the public, paginated `GET /api/notes` search API over the new `data/dialects_user.db` notes data, including independent location and partition scope resolution.

**Architecture:** A standalone notes service queries `notes` and `notes_fts` in `data/dialects_user.db`; it resolves raw locations and partitions against `data/query_user.db` before applying the `notes.簡稱` filter. It may use the existing low-level geo matching and partition primitives, but it must not import or invoke `/api/search_chars` or `search_characters`. A dedicated router is mounted at `/api`, rather than under the vocabulary router.

**Tech Stack:** FastAPI, Pydantic, SQLite/FTS5, existing SQLite connection pool, `run_in_threadpool`, pytest.

---

## Current database facts

- Runtime database paths are `data/dialects_user.db` and `data/query_user.db`; the repository-root `query_user.db` is an empty stale file and must never be used.
- `notes` has 213,806 rows; 212,817 valid rows (`註釋` nonblank and not `_`/`-`) across 2,068 abbreviations.
- Every valid note abbreviation maps through `query_user.db.dialects.簡稱`, with nonblank `地圖集二分區` and `音典分區`.
- `notes_fts` is contentless FTS5, so tests must query it with `MATCH`; they must not try to scan it with `COUNT(*)`.

### Task 1: Build the independent notes-query service with test-first SQL behavior

**Files:**

- Create: `app/service/notes.py`
- Create: `tests/test_notes_service.py`
- Create: `tests/test_notes_real_database_contract.py`

- [ ] **Step 1: Write the temporary two-database test fixture and failing service tests.**

  Define a notes SQLite fixture with the real raw columns and a contentless FTS5 table. Insert source duplicates, whitespace annotation text, literal `%` IPA, `_`/`-` sentinels, and notes at two mapped abbreviations. Define a query SQLite fixture with `dialects(簡稱, 地圖集二分區, 音典分區, 存儲標記)` and all locations marked valid.

  ```python
  def test_detail_search_matches_one_and_two_character_queries(notes_db, query_db):
      assert [item["id"] for item in query_notes(
          q="文白", search_fields=["detail"], locations=None, regions=None,
          region_mode="yindian", page=1, page_size=50,
          notes_db_path=notes_db, query_db_path=query_db,
      )["items"]] == [1, 2]

  def test_ipa_search_treats_percent_as_literal(notes_db, query_db):
      result = query_notes(
          q="pa%", search_fields=["pronunciation"], locations=None, regions=None,
          region_mode="yindian", page=1, page_size=50,
          notes_db_path=notes_db, query_db_path=query_db,
      )
      assert [item["ipa"] for item in result["items"]] == ["pa%"]
  ```

  Add assertions for: invalid/blank query and unsupported field rejection; `all`/empty fields searching both branches; a source row found by both branches returned once; duplicate-looking source rows retained; rowid order and page 2; blank scope searching globally; map/yindian region expansion; explicit+region union; and supplied scope resolving to zero returning an empty response.

  In `tests/test_notes_real_database_contract.py`, add an integration test that skips only when either runtime `data/` database is missing. It imports the same service and asserts a one-character detail query and a top-level-region query with `page_size=1` each return a well-formed page. It must use `data/query_user.db`, never root `query_user.db`.

- [ ] **Step 2: Run the focused test file and verify RED.**

  Run: `pytest tests/test_notes_service.py tests/test_notes_real_database_contract.py -q`

  Expected: collection fails because `app.service.notes` does not exist.

- [ ] **Step 3: Implement only the service required by the failing tests.**

  Export these explicit seams:

  ```python
  SEARCH_FIELDS = frozenset({"pronunciation", "detail"})

  def parse_notes_search_fields(values: list[str] | None) -> set[str]:
      """Validate fields; absent, empty, or all selects both valid fields."""

  def resolve_notes_scope(locations, regions, region_mode, query_db_path) -> tuple[bool, list[str]]:
      """Return whether a nonempty raw scope was supplied and its resolved abbreviations."""

  def query_notes(*, q, search_fields, locations, regions, region_mode,
                  page, page_size, notes_db_path, query_db_path) -> dict:
      """Return the requested notes page and total using the supplied database paths."""
  ```

  `resolve_notes_scope` must independently call `match_locations_batch_all` with `exact_only=True` and `query_dialect_abbreviations`; it must not import `app.service.core.search_chars` or `search_characters`. Its boolean records whether the request supplied any nonblank scope value, so `[]` means all data only when the scope was absent, never when matching failed. This follows `/api/search_chars`' exact location handling without importing that route or service.

  Build selected FTS and IPA rowid subqueries, join them with `UNION`, apply the valid-annotation predicate in every active branch, and add a parameterized `notes.簡稱 IN` predicate only when the resolved scope is nonempty. Use the same matched CTE for `COUNT(*)` and the page query, ordered by `notes.rowid ASC`.

- [ ] **Step 4: Run focused service tests and inspect the query plan.**

  Run:

  ```bash
  pytest tests/test_notes_service.py tests/test_notes_real_database_contract.py -q
  sqlite3 data/dialects_user.db "EXPLAIN QUERY PLAN SELECT rowid FROM notes WHERE 簡稱 = '1883廈門'"
  ```

  Expected: all service tests pass; the real database query plan uses `idx_notes_abbr` for abbreviation filtering.

- [ ] **Step 5: CR and commit the service step.**

  Run `git diff --check`, inspect `git diff -- app/service/notes.py tests/test_notes_service.py tests/test_notes_real_database_contract.py`, verify no build database or unrelated files changed, then commit only these files:

  ```bash
  git add app/service/notes.py tests/test_notes_service.py tests/test_notes_real_database_contract.py
  git commit -m "feat: add notes search service"
  ```

### Task 2: Expose the public `/api/notes` route without vocabulary or search-chars coupling

**Files:**

- Create: `app/routes/notes.py`
- Create: `app/schemas/notes.py`
- Modify: `app/routes/__init__.py`
- Modify: `app/common/api_config.py`
- Create: `tests/test_notes_route.py`

- [ ] **Step 1: Write failing route, model, registration, and policy tests.**

  Test that the OpenAPI application registers `GET /api/notes`, the route accepts repeated `locations`/`regions`, uses page defaults, and returns the following response model shape:

  ```python
  {
      "items": [{"id": 1, "location_name": "A", "character": "字", "ipa": "pa", "notes": "注"}],
      "total": 1,
      "page": 1,
      "page_size": 50,
  }
  ```

  Mock only the notes service at the router boundary. Also assert `match_route_config("/api/notes")` is public and rate-limited, and `/api/notes` is included in usage recording rather than relying on `/api/vocabulary/*`.

- [ ] **Step 2: Run the route tests and verify RED.**

  Run: `pytest tests/test_notes_route.py -q`

  Expected: the route path and notes Pydantic models are absent.

- [ ] **Step 3: Add the isolated route, schemas, route registration, and exact policy.**

  Define `NotesItemResponse` and `NotesSearchResponse` in `app/schemas/notes.py`. In `app/routes/notes.py`, declare `@router.get("/notes", response_model=NotesSearchResponse)`, validate `region_mode` as `map | yindian`, get only server-configured database paths through dependencies, and call `query_notes` through `run_in_threadpool`.

  Register `notes_router` in `app/routes/__init__.py` with `prefix="/api"`, tag `"Notes"`, and the existing `ApiLimiter` dependency. Add one exact `/api/notes` config entry with `rate_limit=True`, `require_login=False`, `log_params=True`, `log_body=False`, and add the exact endpoint to `RECORD_API`.

- [ ] **Step 4: Run route and focused regression tests.**

  Run:

  ```bash
  pytest tests/test_notes_route.py tests/test_notes_service.py -q
  pytest tests/test_vocabulary_routes.py -q
  ```

  Expected: the new route is public/rate-limited, bad parameters return 400, and existing vocabulary routes remain unchanged.

- [ ] **Step 5: CR and commit the route step.**

  Inspect `git diff --check` and the five-file diff, confirm the `/api/vocabulary` router has not gained this endpoint, then commit:

  ```bash
  git add app/routes/notes.py app/schemas/notes.py app/routes/__init__.py app/common/api_config.py tests/test_notes_route.py
  git commit -m "feat: expose notes search API"
  ```
