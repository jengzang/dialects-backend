# Cluster Single-Instance Executor Plan

> For Hermes: use requesting-code-review after each implementation batch before committing.

Goal: move cluster execution from request-worker BackgroundTasks to one shared serial executor so main workers only enqueue jobs and return immediately.

Architecture: keep the current HTTP contract, task_manager, staged artifact hashes, and cache services; replace in-worker background execution with a file-backed pending queue plus one in-process singleton executor loop started only once in the main Gunicorn master lifecycle. The executor claims queued jobs serially and runs the existing cluster/staged service functions unchanged as much as possible.

Tech Stack: FastAPI, Gunicorn master hooks, Python threading, file_manager/task_manager, existing cluster staged/cache services.

---

## Scope boundaries

In scope:
- cluster job execution path only
- staged prepare/distance/cluster execution path only
- single-instance serial executor (concurrency = 1)
- main app lifecycle start/stop integration
- scoped verification and commit

Out of scope:
- GIS changes
- changing cluster algorithms
- changing public route schemas
- multi-host distributed execution
- parallel cluster executor pool

---

## Current grounded findings

1. Current cluster routes enqueue execution via FastAPI BackgroundTasks in request workers.
   - File: `app/tools/cluster/routes.py`
   - Endpoints using `background_tasks.add_task(...)`:
     - `POST /api/tools/cluster/jobs`
     - `POST /api/tools/cluster/staged/prepare`
     - `POST /api/tools/cluster/staged/distances`
     - `POST /api/tools/cluster/staged/clusters`

2. Cluster already has the right persistence seams for service-ization.
   - File-based task state: `app/tools/task_manager.py`
   - File/artifact storage root: `app/tools/file_manager.py`
   - Hash-addressed staged artifacts: `app/tools/cluster/service/staged_session_service.py`
   - Cached/inflight helpers: `app/tools/cluster/service/cache_service.py`

3. Cluster computation is not lightweight logging-style work.
   - `app/tools/cluster/service/cluster_service.py` imports `numpy as np`
   - staged service reads/writes `npy/npz/json`
   - therefore the executor should be a dedicated serial worker loop, not a logging-style queue consumer thread multiplexing many tiny events

4. Main lifecycle already has a place to start one shared background service.
   - File: `app/lifecycle/background.py`
   - `start_background_services()` is called once from `gunicorn_main.py:on_starting`
   - this is the right place to start one cluster executor loop

---

## Target design

### Runtime model

- main Gunicorn master starts one cluster executor loop exactly once
- request workers never run cluster computation directly
- request workers only:
  - validate and normalize payload
  - create/update task records
  - enqueue a file-backed job descriptor
  - return task id / pending status
- executor loop:
  - scans pending queue
  - atomically claims one job
  - dispatches to the existing service entrypoints with the arguments each stage really needs
  - updates task_manager/result artifacts
  - moves job to completed or failed terminal metadata
- queue concurrency is strictly 1

### Why this matches the user's goal

- cluster becomes a shared single instance like the logging sidecar in spirit
- main workers are released quickly for other requests
- cluster peak memory is concentrated in one executor instead of spreading across request workers
- concurrent cluster submissions queue rather than fan out into multiple heavy compute copies

---

## File changes

### Create
- `app/tools/cluster/executor_queue.py`
- `app/tools/cluster/executor_runtime.py`
- `tests/test_cluster_executor_queue.py`
- `tests/test_cluster_routes_executor_mode.py`

### Modify
- `app/tools/cluster/config.py`
- `app/tools/cluster/routes.py`
- `app/lifecycle/background.py`
- possibly `app/tools/file_manager.py` only if a tiny helper is truly needed; avoid if not necessary

---

## Job envelope design

Use file-backed queue entries under the cluster tool directory, for example:
- `<tool_dir>/_executor/pending/<job_id>.json`
- `<tool_dir>/_executor/processing/<job_id>.json`
- `<tool_dir>/_executor/completed/<job_id>.json`
- `<tool_dir>/_executor/failed/<job_id>.json`

Envelope shape:
```json
{
  "job_id": "cluster_exec_xxx",
  "job_type": "cluster_job|staged_prepare|staged_distance|staged_cluster",
  "task_id": "cluster_xxx",
  "created_at": 0.0,
  "payload": {
    "dialects_db": "...",
    "query_db": "...",
    "phoneme_mode": "...",
    "distance_hash": "...",
    "clustering_config": {...}
  }
}
```

Notes:
- keep payload minimal; do not duplicate large staged artifacts
- use existing hashes and task ids as the source of truth
- job_type decides which existing service function to call

---

## Task list

### Task 1: Add executor queue constants

Objective: define stable queue directory names and polling interval.

Files:
- Modify: `app/tools/cluster/config.py`

Steps:
1. Add constants for executor queue root and subdirs.
2. Add serial poll interval constant.
3. Keep names cluster-specific and storage-agnostic.
4. Run `python -m py_compile app/tools/cluster/config.py`.

### Task 2: Implement file-backed queue helpers

Objective: create atomic enqueue/claim/finish helpers without touching compute code.

Files:
- Create: `app/tools/cluster/executor_queue.py`
- Test: `tests/test_cluster_executor_queue.py`

Steps:
1. Write failing tests for:
   - enqueue creates pending json
   - claim_next_job atomically moves one job to processing
   - complete_job / fail_job move job to terminal dir
2. Implement helpers:
   - `enqueue_job(...)`
   - `claim_next_job()`
   - `mark_job_completed(...)`
   - `mark_job_failed(...)`
   - `iter_pending_jobs()` if useful
3. Use atomic rename/replace semantics.
4. Run scoped tests.

### Task 3: Implement singleton executor runtime

Objective: add one serial loop that consumes queue jobs and dispatches to existing cluster services.

Files:
- Create: `app/tools/cluster/executor_runtime.py`
- Test: `tests/test_cluster_routes_executor_mode.py` (partly mocked)

Steps:
1. Add runtime state:
   - started flag
   - stop event
   - thread handle
   - lock
2. Implement:
   - `start_cluster_executor()`
   - `stop_cluster_executor()`
   - worker loop that claims one job at a time
3. Dispatch by `job_type`:
   - `cluster_job` -> existing `run_cluster_job(task_id, dialects_db, query_db)`
   - `staged_prepare` -> existing `run_prepare_task(task_id)`
   - `staged_distance` -> existing `run_distance_task(task_id, phoneme_mode)`
   - `staged_cluster` -> existing `run_cluster_task(task_id, distance_hash, clustering_config)`
4. Mark queue entry completed/failed around execution.
5. Keep error logging explicit and task status truthful.
6. Run py_compile and mocked unit tests.

### Task 4: Wire executor into main lifecycle

Objective: start exactly one executor with the same shared-background pattern as logging/scheduler.

Files:
- Modify: `app/lifecycle/background.py`

Steps:
1. Import executor runtime lazily inside lifecycle functions.
2. In `start_background_services()`, start the cluster executor once.
3. In `stop_background_services()`, stop the cluster executor cleanly.
4. Keep main-only lifecycle semantics unchanged.
5. Run py_compile.

### Task 5: Replace BackgroundTasks in cluster routes

Objective: enqueue jobs instead of executing on request workers.

Files:
- Modify: `app/tools/cluster/routes.py`
- Test: `tests/test_cluster_routes_executor_mode.py`

Steps:
1. Remove `BackgroundTasks` dependency from cluster execution endpoints where no longer needed.
2. In `POST /jobs`, after task creation and inflight handling, enqueue a `cluster_job` envelope instead of `background_tasks.add_task(...)`.
3. In staged endpoints, enqueue:
   - `staged_prepare`
   - `staged_distance`
   - `staged_cluster`
4. Preserve response payload shape and task ids.
5. Add tests proving route handlers enqueue but do not directly call compute functions.
6. Run scoped tests.

### Task 6: Recovery and stale-processing policy

Objective: make executor startup safe if the process restarts mid-job.

Files:
- Modify: `app/tools/cluster/executor_queue.py`
- Modify: `app/tools/cluster/executor_runtime.py`
- Test: `tests/test_cluster_executor_queue.py`

Steps:
1. On executor start, scan `processing/` jobs.
2. Requeue them to pending OR fail them deterministically; choose one behavior and document it in code comments.
3. Initial recommendation: requeue processing jobs on startup because task/artifact writes are already idempotent-ish around hashes and cache checks.
4. Add tests for startup recovery behavior.

### Task 7: Scoped CR and verification

Objective: run the required review gates before commit.

Files:
- No code scope expansion; verify only touched files.

Steps:
1. Run py_compile on changed modules.
2. Run targeted tests for queue/runtime/routes.
3. Run `git diff --check`.
4. Run independent reviewer using requesting-code-review skill.
5. Fix any blocking issues and rerun verification.

### Task 8: Scoped commit

Objective: commit only the cluster executor work.

Steps:
1. Inspect `git status --short`.
2. Stage only cluster/lifecycle/tests/docs files belonging to this task.
3. Verify staged set with:
   - `git diff --cached --stat`
   - `git diff --cached --name-only`
4. Commit with a scoped message.

---

## Acceptance checks

Functional:
- creating cluster jobs no longer uses FastAPI BackgroundTasks
- creating staged prepare/distance/cluster tasks no longer uses BackgroundTasks
- one executor loop can consume queued jobs and run existing compute functions
- task status/result paths continue to work through existing APIs
- inflight/result cache behavior is preserved

Isolation:
- request worker returns immediately after enqueue
- cluster execution happens outside request worker flow
- only one cluster job executes at a time in this first version

Verification:
- scoped tests pass
- py_compile passes for modified modules
- independent code review returns pass

---

## Important implementation constraints

- do not change public route schemas unless forced
- do not refactor cluster algorithms in the same patch
- prefer lazy imports in executor runtime so main startup only pays for executor scaffolding, not cluster compute before first job
- preserve existing task ids and staged hash semantics
- preserve cache-hit fast paths exactly

---

## Code review checkpoints the user requested

CR checkpoint 1:
- after queue/runtime skeleton lands

CR checkpoint 2:
- after routes switch from BackgroundTasks to enqueue mode

CR checkpoint 3:
- final verification before commit
