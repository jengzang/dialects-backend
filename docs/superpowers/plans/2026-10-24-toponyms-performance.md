# Toponyms performance implementation plan

**Goal:** Optimize /api/toponyms/* for 2 CPU / 2 GB while preserving complete unlimited results.
**Architecture:** Read-only SQLite, file-backed temporary sorting, bounded cross-process work,
batched administrative path loading, streamed JSON for full results and small-result caching.
**Tech Stack:** FastAPI, sqlite3, AnyIO/asyncio, POSIX flock, unittest/pytest.

User clarification overrides the original proposal: limit=0 must remain unlimited.
No output cap, forced pagination, deep-page rejection or full-stream duration budget.

- [x] Establish baseline and failing regression tests for full administrative loading and resource control.
- [x] Replace all-division loading with batch code/ancestor queries and indexed parent-path traversal.
- [x] Probe the existing 5000-pair tree threshold and expose an explicit count lower bound.
- [x] Reuse the existing type/name/id covering index for points, with missing-index fallback.
- [x] Avoid unused search fields and deduplicate/batch detail ancestor loading.
- [x] Preserve limit=0 and positive limit<=2,000,000; stream unlimited and >5000-row requests in 256-row batches.
- [x] Add shared heavy=2/tree=1/light=1 execution slots, read-only 4 MiB connections, file temp store.
- [x] Handle disconnects during initial SQL and during output; do not release slots before SQL stops.
- [x] Add bounded small-result cache/singleflight; bypass full result caching and automatic retries.
- [x] Test full matching/ordering across modes, types and bbox; validate real middleware and gzip.
- [x] Measure full queries on the local real database, without modifying it.
- [x] Independent review: reproduce and fix initial disconnect through BaseHTTPMiddleware.
- [x] Final verification: 46 relevant tests passed; baseline-only failures documented. No deployment, push or schema/index modification.
