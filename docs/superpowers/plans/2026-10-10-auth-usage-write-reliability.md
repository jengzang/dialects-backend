# Auth usage write reliability implementation plan

**Goal:** Reduce lost auth usage events during SQLite contention, queue overflow and graceful shutdown without changing database schemas or requiring another service.

**Architecture:** Keep the existing detail and summary queues. Retry confirmed SQLite lock errors after rollback. Preserve failed events in private, atomically published JSON files under `logs/auth-usage-recovery`; files are evidence for manual reconciliation, not an automatic replay queue. Flush batches within two seconds of their first event and join logging threads during shutdown.

**Limits:** Normal queued events are still volatile on a forced process exit. Detail and summary remain independent transactions. Recovery-file writes can fail when storage is unavailable; report these explicitly and retain background batches in memory. Do not automatically replay summary counters without event deduplication.

**Tech stack:** Python, SQLAlchemy, SQLite, multiprocessing queues, pytest.

## Tasks

- [x] Add failing tests with temporary databases for lock retry, permanent failure preservation, overflow preservation, batch deadlines and shutdown draining.
- [x] Set an explicit SQLite busy timeout; retry only SQLite BUSY/LOCKED errors after rollback, with bounded backoff. Save non-retryable or exhausted batches rather than discarding them.
- [x] Preserve overflowing auth detail/summary events in recovery files. Share the auth enqueue implementation with traffic middleware to avoid duplicate behavior.
- [x] Flush detail/summary batches on a monotonic first-event deadline. Retain batches if both database and recovery-file writes fail.
- [x] Track worker handles; deliver stop sentinels with bounded waits and join workers against one shutdown deadline. Report timeouts rather than claim workers stopped.
- [x] Run focused tests and suggestion/session regressions; review diff for transaction safety and compatibility. Document recovery files and the remaining durability limits.

## Verification

Use temporary SQLite databases only for failure tests. Hold a real write lock and release it during retry; verify exactly one detail row / one summary increment. Test a permanent failure and a full queue by reading preserved JSON. Exercise continuous arrivals past the flush deadline and shutdown with a full queue. Run `.venv/bin/python -m pytest tests/test_auth_usage_reliability.py tests/test_user_suggestions.py tests/test_admin_session_stats.py -q` with temporary files inside the workspace.

## Results

38 targeted tests passed (22 reliability tests plus suggestion and session regressions), including real SQLite contention, exhausted retries, invalid foreign keys, full/closed queues, recovery-storage failure, unconfirmed rollback, first-event deadlines, shutdown timeouts and actual HTTP tracking. Existing dependency/API deprecation warnings remain. Independent review findings about test import isolation, incomplete shutdown restart and post-publication directory sync were resolved and covered by regression tests. `git diff --check` passed. No database migration or server deployment was performed.
