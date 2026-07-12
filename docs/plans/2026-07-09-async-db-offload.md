# Async DB Offload Implementation Plan

> **For Hermes:** Use executing-plans skill to implement this plan task-by-task.

**Goal:** Prevent selected async FastAPI routes from blocking the event loop while they run synchronous SQLite/pandas/service database work.

**Architecture:** Keep route contracts unchanged. Do not migrate the project to async DB drivers. For target routes that must remain `async def`, move synchronous database-heavy work behind `asyncio.to_thread(...)`, with the DB connection/session opened inside the worker thread where possible.

**Tech Stack:** FastAPI, sqlite3, SQLAlchemy sync Session, pandas, asyncio.to_thread, existing SQLite connection pool.

---

## Why asyncio.to_thread here

`asyncio.to_thread` will not make one SQLite query faster. Its benefit is concurrency isolation:

1. It keeps the uvicorn worker event loop free while the blocking DB call runs in a worker thread.
2. Other async requests handled by the same uvicorn worker can continue to progress if they do not need the same exhausted resource.
3. It matches the existing style already used in `core/phonology.py`, `core/matrix.py`, `core/search.py`, `core/compare.py`, `core/new_pho.py`, and `geo/get_coordinates.py`.
4. It is lower-risk than introducing aiosqlite because much of this code uses sqlite3, pandas, and sync SQLAlchemy.

Important boundary: this is not per-query speedup. SQLite still runs the same query. If too many long queries are scheduled, the threadpool can also saturate. The value is preventing event-loop starvation.

## Current findings

Already offloaded / acceptable:
- `app/routes/core/search.py`: already uses `run_in_threadpool` for location matching, search, tones, custom data.
- `app/routes/core/compare.py`: compare chars/tones and ZhongGu heavy pieces already use `run_in_threadpool`.
- `app/routes/core/new_pho.py`: charlist/ZhongGu/YinWei heavy service calls already use `run_in_threadpool`.
- `app/routes/geo/get_coordinates.py`: already uses `run_in_threadpool` and creates thread-local custom DB session.

Needs change:
- `app/sql/sql_tree_routes.py`: `/tree/full` and `/tree/lazy` are async endpoints with direct sqlite3 calls.
- `app/sql/sql_routes.py`: `/query`, `/query/columns`, `/query/count`, `/distinct/...`, `/distinct-query` are async endpoints with direct sqlite3 calls.
- `app/routes/core/phonology.py::feature_counts`: async endpoint directly calls sync service.

Out of scope by user decision:
- `app/sql/sql_admin_routes.py`: admin-only and low usage.

## Tasks

### Task 1: Offload sql_tree_routes

Files:
- Modify `app/sql/sql_tree_routes.py`
- Test `tests/test_sql_tree_full_precheck.py`

Steps:
1. Import `asyncio`.
2. Extract current `get_full_tree` body into `_get_full_tree_sync(params, user, auth_db)`.
3. Make route `get_full_tree(...)` return `await asyncio.to_thread(_get_full_tree_sync, params, user, auth_db)`.
4. Extract current `get_tree_children` body into `_get_tree_children_sync(params, user, auth_db)`.
5. Make route `get_tree_children(...)` return `await asyncio.to_thread(_get_tree_children_sync, params, user, auth_db)`.
6. Keep existing count precheck behavior and lazy fallback response unchanged.
7. Run `tests.test_sql_tree_full_precheck`.

### Task 2: Offload sql_routes

Files:
- Modify `app/sql/sql_routes.py`
- Create/modify tests for basic route helper behavior if practical.

Steps:
1. Import `asyncio` and `Any` as needed.
2. Add small sync helpers that open DB connections inside the thread:
   - `_query_table_page_sync(...)`
   - `_query_table_count_sync(...)`
   - `_get_column_info_sync(...)`
   - `_get_table_count_sync(...)`
   - `_get_distinct_path_values_sync(...)`
   - `_get_distinct_query_values_sync(...)`
3. In async routes, keep Redis cache reads/writes in async context.
4. Wrap only blocking DB work with `await asyncio.to_thread(...)`.
5. Preserve validation, SQL parameterization, response shapes, cache keys, and errors.

### Task 3: Offload feature_counts

Files:
- Modify `app/routes/core/phonology.py`

Steps:
1. Replace direct `get_feature_counts(locations, dialects_db)` with `await asyncio.to_thread(get_feature_counts, locations, dialects_db)`.
2. Leave Redis-backed feature_stats untouched because it already offloads.

### Task 4: Verify target modules

Run:
- `.venv/bin/python -m unittest tests.test_sql_tree_full_precheck -v`
- `.venv/bin/python -m py_compile app/sql/sql_tree_routes.py app/sql/sql_routes.py app/routes/core/phonology.py app/routes/core/search.py app/routes/core/compare.py app/routes/core/new_pho.py app/routes/geo/get_coordinates.py tests/test_sql_tree_full_precheck.py`

### Task 5: Review and commit

Steps:
1. Inspect `git diff` for only intended files.
2. Run security grep for added SQL interpolation risks.
3. Stage only changed files.
4. Verify staged names/stat.
5. Commit with a scoped message.
