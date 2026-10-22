# Remove the cluster tool from dev

**Baseline:** `71972d6`, preserved by `dev-with-cluster` before removal.

**Goal:** Remove `/api/tools/cluster`, its executor and dedicated Numba dependency without affecting vocabulary caching, villagesML, Praat or other tools. The user approved this scope and will rebuild the image themselves.

## Plan

- Add regression checks for absence of cluster routes and imports, and for background startup/shutdown without cluster while retaining existing services.
- Remove `app/tools/cluster`, its standalone app/startup/route registrations, Numba bootstrap calls and module, the Numba requirement, and cluster-only tests/smoke scripts.
- Remove the Docker Numba environment setting. Keep `libgomp1`: scikit-learn and other native libraries remain in use. Exclude Python/Numba cache files recursively from the build context.
- Keep NumPy, SciPy, scikit-learn, NetworkX, Praat and villagesML routes. Retain shared legacy cluster cleanup policies so existing artifacts can expire normally; do not delete production data or Redis keys.
- Verify imports and routes with Numba/llvmlite/cluster imports explicitly blocked, verify background lifecycle, run cleanup/villagesML/vocabulary regression tests, and inspect the final diff. Do not build an image or push branches.

## Resource behavior

No new workers, threads, queues, caches, services or retries. Cluster no longer creates a polling thread or accepts/enqueues work, including previously queued work. Existing non-cluster concurrency and cache bounds remain unchanged. Legacy cleanup keeps its existing five-minute interval and limits. Historical cluster data is not immediately reclaimed. File-size and memory savings remain subject to the user's eventual rebuild and deployment.

## Verification

- Both new regression checks failed against the original implementation because it imported `app.tools.cluster`, then passed after removal.
- Targeted checks for cluster removal, shared cleanup, real Redis vocabulary caching, warmup lifecycle, cache routes and local startup helpers: 56 passed. Redis ran in a temporary container limited to 0.25 CPU / 64 MiB with persistence disabled.
- villagesML query/schema checks: 19 passed and 8 failures (including a subtest). The same failures reproduced against an isolated export of the unmodified `dev-with-cluster` baseline. No villagesML production code was changed.
- Follow-up route comparison: 348 registrations before removal, 339 after. Exactly nine cluster registrations disappeared; every other path, HTTP method set and endpoint name was preserved.
- Broader follow-up suite (excluding the pre-existing untracked admin test, using temporary Redis): 401 passed, 37 failures including a subtest. Every currently failing test node also failed on the isolated backup baseline; no failing node was unique to removal. The baseline export had additional failures/skips because it lacked local data. This does not establish production or rebuilt-image correctness.
