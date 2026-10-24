# Vocabulary performance implementation plan

**Goal:** Implement the user's approved three-part performance fixes with no frontend/API changes, no result truncation and no persistent schema changes.
**Architecture:** Preserve the existing response contracts and filter builder. Reduce query intermediates, cache exact counts using existing revision fencing, use disk staging for uploads and file-backed exports, and bound synchronous background work across workers on this single-host 2 CPU / 2 GB deployment.
**Tech stack:** FastAPI, SQLAlchemy, SQLite, Redis, pandas/openpyxl, POSIX file leases.

- [x] Query: iterate standard-word grouped rows; bounded canonical conversion cache; heap selection only for an existing finite limit; full result remains complete. COUNT conditionally omits location JOIN based on actual SQL dependencies. Map aggregates narrow entry rows before metadata joins. Add exact count cache independent of pagination using the existing data revisions.
- [x] Import/parser: preserve file formats, header aliases, row/error order and numeric cell semantics. Accept file streams instead of whole upload bytes; stage parsed rows on disk, CSV chunks and read-only XLSX rows; bulk insert fixed batches in one transaction. Bound old-entry snapshots before materialization. Preserve full error reporting and rollback.
- [x] Execution: move preview and SQL mutation synchronous work off the event loop; bounded single-host admission before thread dispatch, cancellation draining through commit/invalidation, no silent retries of writes. Batch replace uses narrow bounded reads while retaining atomic validation and replacement.
- [x] Export: write XLSX to a temporary file, return the same downloadable content and headers, clean up after completion/disconnection or build error.
- [x] Verify: regression tests for complete results/filter semantics, stale count rejection, event-loop responsiveness, transaction rollback, large import/export completeness and resource cleanup. Run existing vocabulary suites and frontend contract tests where practical. Measure isolated full-result query memory and record limitations.
- [x] Review: independent spec and quality review, resolve findings, document concurrency/buffering/retry behavior and measured results. Integrate verified changes into the user's working branch without altering unrelated files.
