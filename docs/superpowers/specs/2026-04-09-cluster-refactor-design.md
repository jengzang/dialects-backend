# Cluster Tool Refactor Design

## Context

`app/tools/cluster/core.py` has grown to more than 2,000 lines and currently mixes:

- request and group resolution
- location resolution and default filtering
- cache access and SQL loading
- phoneme-distance modeling
- clustering execution
- task/result persistence

This makes algorithm iteration harder than it needs to be. A change to one area currently requires loading unrelated task, SQL, and result-building context into the same file.

The cluster tool already has stable external entry points through:

- `app/tools/cluster/routes.py`
- `app/tools/cluster/__init__.py`

This creates a good opportunity for an internal refactor that keeps the public API stable.

## Goals

- Keep current public behavior and route shape unchanged.
- Split the current `cluster` implementation into focused internal modules.
- Preserve the current `phoneme_mode`, group-weight, and phonetic-weight semantics.
- Keep reuse of `task_manager` and `file_manager`.
- Remove clearly unused legacy helpers during the refactor.

## Non-Goals

- No API redesign.
- No algorithm redesign.
- No semantic changes to `phoneme_mode`, `group_weight`, `use_phonetic_values`, or `phonetic_value_weight`.
- No route restructuring beyond import rewiring.

## Target Structure

The cluster tool will use this structure:

```text
app/tools/cluster/
  __init__.py
  config.py
  routes.py
  schemas/
    __init__.py
    job.py
    result.py
  service/
    __init__.py
    job_service.py
    resolver_service.py
    loader_service.py
    distance_service.py
    pipeline_service.py
    result_service.py
  utils/
    __init__.py
    common.py
    location_utils.py
```

## Responsibilities

### `routes.py`

Thin HTTP layer only:

- request parsing
- dependency injection
- exception translation
- delegation into service entry points

### `config.py`

Central place for cluster constants and defaults, including:

- feature-column mapping
- tone-slot columns
- default filtered yindian regions
- cache TTL
- default phoneme-mode parameters
- numeric constants such as epsilon

### `schemas/job.py`

Request and task-status schemas:

- group request
- clustering request
- job create request/response
- status response

### `schemas/result.py`

Holds reusable result-facing typed structures introduced during the refactor. This file will exist even if it stays small in the first pass, so the package layout is stable from the start.

### `service/resolver_service.py`

Owns request normalization and snapshot building:

- char input normalization
- preset/custom/resolved-char resolution orchestration
- location resolution
- default special-location filtering
- `resolve_cluster_groups`
- `resolve_cluster_job_snapshot`

### `service/loader_service.py`

Owns data access and cache access:

- Redis JSON get/set helpers
- charlist cache reuse
- characters table filter loading
- dialect row loading
- location-detail loading
- dimension inventory profile loading

This service should be the only place that knows how cluster talks to Redis and SQLite.

### `service/distance_service.py`

Owns phoneme-distance logic:

- token alignment
- label-invariant correspondence distance
- structural distance
- aligned phonetic-value distance
- anchored-inventory distance
- shared-request-identity support
- total distance matrix construction

This is the main algorithm module for future clustering iteration.

### `service/pipeline_service.py`

Owns numerical pipeline logic after distances/features exist:

- feature normalization
- MDS
- agglomerative / dbscan / kmeans / gmm execution
- clustering metric calculation
- execution-space selection

### `service/result_service.py`

Owns output assembly:

- public location-detail shaping
- assignment rows
- warnings aggregation
- task summary
- final result payload assembly

### `service/job_service.py`

Acts as the service entry layer for the tool:

- `get_task_status_payload`
- `get_cluster_result`
- `build_task_summary`
- `build_cluster_result`
- `run_cluster_job`

It composes the other services and is the main import target for routes and package exports.

### `utils/`

Only low-level, stateless helpers belong here. No main workflow logic should live in `utils`.

## Import Direction

To keep the module graph understandable, imports should flow in one direction:

- `routes.py` -> `service/job_service.py`
- `service/job_service.py` -> other `service/*`
- `service/*` -> `config.py`, `schemas/*`, `utils/*`

Cross-service imports are allowed when they reflect clear dependency direction, but circular imports must be avoided. Shared low-level helpers should move to `utils/*` rather than creating two-way service dependencies.

## Public Compatibility

These externally used functions remain available through `app/tools/cluster/__init__.py`:

- `build_cluster_result`
- `build_task_summary`
- `get_cluster_result`
- `get_task_status_payload`
- `resolve_cluster_groups`
- `resolve_cluster_job_snapshot`
- `run_cluster_job`

`routes.py` should keep its current route shape and request/response behavior.

## Legacy Cleanup Policy

This refactor may delete internal functions only when both conditions are true:

1. they are no longer used by the active `phoneme_mode` pipeline
2. they are not part of the public import surface

Legacy `metric_mode` request compatibility remains intact. The compatibility behavior stays the same; only dead internal helpers that no longer support the live path may be removed.

## Migration Sequence

1. Create the new directory skeleton.
2. Split `schemas.py` into `schemas/job.py` and `schemas/result.py`.
3. Move configuration constants into `config.py`.
4. Move cache and DB helpers into `loader_service.py`.
5. Move group/location resolution into `resolver_service.py`.
6. Move phoneme-distance logic into `distance_service.py`.
7. Move clustering pipeline helpers into `pipeline_service.py`.
8. Move result assembly helpers into `result_service.py`.
9. Create `job_service.py` as the entry layer and rewire routes/package exports.
10. Remove unused legacy helpers from the old monolith.
11. Shrink or remove the old `core.py` implementation body once all references are updated.

## Verification

The refactor is complete only if all of the following still work:

- schema import and route import succeed
- task creation and background execution still run
- default special-location filtering still works
- `phoneme_mode` values still produce the same behavior
- `group_weight` and `phonetic_value_weight` still work per group
- `preset` and `custom` groups both resolve correctly
- `agglomerative`, `dbscan`, `kmeans`, and `gmm` all still execute
- result loading and task-status loading still work

Minimum verification commands after the refactor:

```bash
python3 -m py_compile app/tools/cluster
git diff --check -- app/tools/cluster
```

Plus real smoke tests against the database for:

- one `preset` request
- one `custom` request
- all three `phoneme_mode` values
- at least one matrix-based algorithm and one embedding-based algorithm

## Recommendation

Implement this as a behavior-preserving structural refactor. Resist the urge to improve formulas or rename public semantics during the split. The immediate goal is to create clean module boundaries so later algorithm work becomes safer and easier to review.
