# Loader Optimization WIP

Status: incomplete

What was completed:
- Analyzed `load_rows` behavior and confirmed the current loader always reads `聲母/韻母/聲調` before later stages select `compare_dimension`.
- Added a local regression test draft for dimension-pruned loading during development, but it is not included in this commit because the implementation was rolled back.
- Verified current SQLite query planning for the temp-table join shape used by `load_dialect_rows`.
- Observed that the current join shape plans as `SCAN dialects` on the 8,150,093-row `dialects` table.
- Compared an alternative `WHERE 簡稱 IN (SELECT ...) AND 漢字 IN (SELECT ...)` query shape and observed that SQLite can use an existing `(簡稱, 漢字, 音節)` index for lookup in that shape.

What is not completed:
- The requested `按请求维度集合加载` implementation is not landed in code.
- No production loader behavior was changed in this commit.
- No new test was committed for the loader optimization yet.

Why it was not completed:
- While implementing the loader change, existing mojibake / encoding-damaged string literals in cluster service files made iterative edits unreliable.
- I rolled the code changes back to avoid pushing a partially corrupted implementation.

Recommended next steps:
1. Re-implement dimension-pruned loading on a clean baseline.
2. Keep the scope behavior-preserving: only load the dimensions actually requested by `groups[*].compare_dimension`.
3. Change the SQL shape for `load_dialect_rows` so SQLite uses the existing `(簡稱, 漢字)` lookup path instead of scanning the whole `dialects` table.
4. Re-run stage timing and then evaluate whether a covering index such as `(簡稱, 漢字, 韻母)` is still worth adding.

Index analysis summary:
- Current indexes already include `(簡稱)`, `(漢字)`, `(簡稱, 漢字)`, `(漢字, 簡稱)`, `(簡稱, 韻母)`, `(簡稱, 聲母)`, `(簡稱, 聲調)`.
- A covering index alone is unlikely to deliver the full benefit if the query shape still drives a full table scan.
- The larger immediate opportunity is query-shape optimization; a covering index is a secondary optimization after the planner is using indexed lookup.
