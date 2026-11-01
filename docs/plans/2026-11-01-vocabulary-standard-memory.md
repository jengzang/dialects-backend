# standard-words 更紧凑的聚合状态

Goal: reduce current scalar-first aggregation memory further without SQL LIMIT, schema changes, standard-word result cache, disk aggregation or frontend changes. Local dev only; preserve other active workspace edits.

Design: compare bounded location bit masks + exact scalar/set overflow, sharing already-identical word/key strings, and releasing group state during full response construction. The first256 nonempty location names get shared bits; excess names retain exact scalar/set membership and may coexist with a mask; after the first overflow, new groups use legacy scalar/set membership to avoid high-diversity CPU regressions, so integer width is bounded at256bits and outputs never truncated. Canonical merging, location-name dedup across users, variants/frequencies, stable ranking, total and unlimited output remain identical. Different normalized groups still require O(groups) state: no claim of constant memory.

- [x] Inspect current implementation and prior measurements; prototype before production changes.
- [x] RED: scalar/mask/overflow transitions at256/257 and many sites, empty locations, repeated locations and users, nonadjacent script variants, tie order, count accuracy, all output, iteration without fetchall; allocation regression against current baseline.
- [x] GREEN: implement accepted compact representation only after correctness tests fail as expected.
- [x] Benchmark actual before/after service functions on current95,003, row growth475,015 and spelling growth199,825 groups; limit1000 and None; filtered/small/full cases, synthetic >256 places. Separate time/RSS/heap, bounded2CPU/2GiB/no swap local containers; no benchmark on server. Include SQL hash/equality and complete output equality.
- [x] Run targeted/full vocabulary regressions with real disposable Redis, reproduce current baseline failures without changing unrelated code. Review source and bounds; commit scoped production/test changes and report.

Resources: no added workers/threads/tasks/cache/retries. Existing admission limits unchanged. Request-local dictionary at most256 named bits; mask <=256bits; overflow scales with true distinct excess names in affected groups, never a cap on results. Peak response memory still grows with full output. Query errors propagate; same existing read/snapshot lifecycle. Online requests pay extra lookup/bit operations, so retain only if actual timings/memory justify this on2c2g. No additional application temp files.

Evidence: implementation e7a2e19; 84 focused passes; full real-Redis run 709 passes / 6 baseline-reproduced failures; all40 paired cases have identical full ordered responses, total and SQL. Report: docs/vocabulary-standard-memory-release-2026-11-01.md. VmHWM (not inherited ru_maxrss) measures peak process RSS; 1024-location full output has6.9% timing regression and is disclosed.
