# Vocabulary follow-up implementation plan

Approved scope: four independent performance changes, local implementation and
tests only, separate commits after independent code review. Baseline: 29ebfa0.
No branch creation, server connection, schema change or new result cache.

## Invariants

- Exact totals, full pagination, unrestricted aggregate/map results, existing
  simplified/traditional matching, ordering and response schemas remain intact.
- Existing two heavy slots / one expensive slot remain; no extra workers,
  background tasks, retries or resident services. Page buffers remain <=200 rows;
  aggregate state still scales with actual groups, with smaller objects.
- SQL sort/group temp B-trees remain SQLite-managed; no application disk
  aggregation and no temp_store configuration changes.

## 1. Entries

- [x] Write and run failing tests in `tests/test_vocabulary_first_page.py` for
  skipping COUNT on a short first page, exact full-page counts, cached zero,
  independent count reuse, fallback paths and a concurrent WAL writer.
- [x] In `query.py`, add a private cache resolver accepting a lazy computation;
  retain the existing two-argument count loader for compatibility. On a cold
  first page, only literal location + headword or definition/headword searches
  may load the page before counting. Infer total only below page_size. Use a
  read savepoint for the page/count miss computation. Cache hits load no page
  inside the computation. Keep all unmeasured shapes on count-first.
- [x] In `cache.py`, pass this lazy computation to the existing count cache.
- [x] Run focused query/cache tests; independently review diff; fix; commit.

## 2. Standard-word SQL

- [x] Write failing tests for extending the identity traversal only to literal
  location searches with headword or definition/headword. Check full results,
  wildcard/overlap/metadata fallbacks, one-shot iterable inputs.
- [x] Add a separate guard in `query.py`, preserving entries' existing guard and
  standard-word covering paths. No global predicate reorder or index change.
- [x] Run focused tests; independently review diff; fix; commit.

## 3. Standard-word compact groups

- [x] Write tests for exact variants/counts/location de-duplication, ties,
  interleaved simplified/traditional spellings, empty locations, heap vs full
  sort and unrestricted output. Verify Python allocation reduction separately.
- [x] Store single location/spelling as scalars; promote to set/dict only when
  needed. Preserve variant frequencies and the exact ranking tuple.
- [x] Run focused tests; independently review diff; fix; commit.

## 4. Map SQL

- [x] Write failing tests for literal, unscoped content keywords using a table
  scan and all scoped/wildcard/location-field fallbacks retaining their plans.
  Verify full point/count/order equivalence including orphans and same names.
- [x] Change only the unscoped ordinary content path. Defer automatic wide
  location selection: 22 terms alone does not prove a wide scope, and adding a
  planning COUNT would consume the expected saving.
- [x] Run focused tests; independently review diff; fix; commit.

## Final verification and report

- [x] Compare final committed code with 29ebfa0 on the original local fixture,
  growth fixture and synthetic increasing-spelling fixture. Measure actual
  selected branches, not the previous unrestricted prototypes.
- [x] Replay frozen SQL serially in a native Linux container limited to 2 CPU,
  2 GiB and no swap. Record elapsed time, process RSS and cgroup memory.
- [x] Measure full service runtime, Python allocation peak and process RSS in
  isolated local processes; distinguish these from SQL-only/container numbers.
- [x] Run vocabulary regression tests, identify existing failures by baseline
  comparison, record full-result parity and CR findings with commit hashes.
- [x] Commit benchmark tooling and the report; leave unrelated files untouched.

Completed 2026-11-01: code commits 80d9a94, 7716069, 6fb221c, 403dccf.
Final measurements and test limitations: [release report](../vocabulary-performance-release-2026-11-01.md).
Native SQL RSS is batch-level only; per-query RSS comes from separate service runs.
