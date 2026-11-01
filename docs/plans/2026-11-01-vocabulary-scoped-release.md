# Bounded vocabulary scope implementation plan

Goal: implement approved location-first prototype without changing result semantics.
Baseline b8d90fe. Local dev only, no branches, server access or schema changes.
Use inline execution, TDD, independent CR before each code commit.

- [x] Add failing tests in tests/test_vocabulary_scope_plan.py: selective scope uses existing index seeks, exact ordered entries/totals, cached/legacy loaders skip planning, parameter key remains stable, standard unlimited and map output equals fallback, orphan/name/metadata overlaps, 257 names/identities trigger fallback, broad scope falls back, WAL writer sees one reader snapshot and error cleanup preserves caller transaction.
- [x] Add app/service/vocabulary/scope_plan.py: bounded 257 distinct-name seeks, bounded 257 extra metadata identities, existing-index coverage probe bounded by min(32768,max(1024,total/10))+1. Return request-local scope only if small; no ids materialization, retries, extra worker or disk aggregation. Reuse resolved VALUES rows in count/page/group SQL.
- [x] Integrate entries in query.py only inside lazy count miss callback, only first-page literal scoped definition/headword/both without other filters. Keep original count SQL/values as cache signature; cache hits/legacy loader use original page. One read SAVEPOINT contains scope planning/page/count; fallback retains old SQL.
- [x] Integrate standard-words and map-points using the same bounded scope, only approved literal content fields and locations, with a read snapshot from planning through SQL execution. Preserve original aggregate columns/order and unlimited results, and consume SQLite cursor as before. Other filters retain old paths.
- [x] Update older plan-sensitive tests only where the newly approved path intentionally replaces the old plan. Run focused and full vocabulary tests with disposable loopback Redis; identify six previously reproduced baseline failures separately.
- [x] Independent review and separate commits for entries/shared planner, standard-words and map-points.
- [x] Benchmark actual final vs b8d90fe: current 95003, row growth 475015, high-hit fixture; fields/scopes/zero-hit/full pages/count-hit fallbacks. Fresh processes for service time and RSS, separate Python heap where needed. Replay actual frozen SQL on native ARM 2 CPU / 2 GiB / no swap, include planning; no server tests.
- [x] Validate all results, capture final source hashes, report SQL vs service/memory limits and any regressions. Review/commit artifacts, stop only test Redis, preserve unrelated user files.

Completed: a1cdceb (entries/planner), 5371580 (standard), 53c865a (map).
Final report: [vocabulary-scoped-release-2026-11-01.md](../vocabulary-scoped-release-2026-11-01.md).
599 passed, six independently reproduced baseline failures; final artifact CR no P1/P2.
