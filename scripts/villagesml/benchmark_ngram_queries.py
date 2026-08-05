from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.common.path import DB_MAPPING


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    sql: str
    params: tuple[Any, ...]


def _clean_sql(sql: str) -> str:
    return " ".join(sql.split())


def build_default_cases(
    *,
    region: str,
    ngram: str,
    n: int,
    position: str = "all",
    level: str = "township",
    limit: int = 100,
) -> list[BenchmarkCase]:
    return [
        BenchmarkCase(
            name="frequency_top_by_n_position",
            sql="""
            SELECT ngram, position, frequency, percentage
            FROM ngram_frequency
            WHERE n = ? AND position = ?
            ORDER BY frequency DESC
            LIMIT ?
            """,
            params=(n, position, limit),
        ),
        BenchmarkCase(
            name="regional_top_by_level_n_region",
            sql="""
            SELECT region AS region_name, city, county, township, ngram, frequency, percentage
            FROM regional_ngram_frequency
            WHERE n = ? AND level = ? AND region = ?
            ORDER BY frequency DESC
            LIMIT ?
            """,
            params=(n, level, region, limit),
        ),
        BenchmarkCase(
            name="tendency_top_by_level_region",
            sql="""
            SELECT level AS region_level, region AS region_name, city, county, township,
                   ngram, n, position, lift AS tendency_score, log_odds, z_score,
                   regional_count AS frequency, regional_total, regional_total_raw,
                   global_count AS expected_frequency, global_total
            FROM ngram_tendency
            WHERE level = ? AND region = ?
            ORDER BY lift DESC
            LIMIT ?
            """,
            params=(level, region, limit),
        ),
        BenchmarkCase(
            name="tendency_by_ngram_across_regions",
            sql="""
            SELECT level AS region_level, region AS region_name, city, county, township,
                   ngram, n, position, lift AS tendency_score, log_odds, z_score,
                   regional_count AS frequency, regional_total, regional_total_raw,
                   global_count AS expected_frequency, global_total
            FROM ngram_tendency
            WHERE level = ? AND ngram = ?
            ORDER BY lift DESC
            LIMIT ?
            """,
            params=(level, ngram, limit),
        ),
        BenchmarkCase(
            name="regional_broad_scan_all_townships",
            sql="""
            SELECT region AS region_name, city, county, township, ngram, frequency, percentage
            FROM regional_ngram_frequency
            WHERE n = ? AND level = ?
            ORDER BY region, frequency DESC
            LIMIT ?
            """,
            params=(n, level, limit),
        ),
        BenchmarkCase(
            name="tendency_broad_scan_all_townships",
            sql="""
            SELECT level AS region_level, region AS region_name, city, county, township,
                   ngram, n, position, lift AS tendency_score, log_odds, z_score,
                   regional_count AS frequency, regional_total, regional_total_raw,
                   global_count AS expected_frequency, global_total
            FROM ngram_tendency
            WHERE level = ?
            ORDER BY lift DESC
            LIMIT ?
            """,
            params=(level, limit),
        ),
    ]


def _plan_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[str]:
    rows = conn.execute(f"EXPLAIN QUERY PLAN {_clean_sql(sql)}", params).fetchall()
    return [" | ".join(str(value) for value in row) for row in rows]


def _execute_once(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> tuple[float, int]:
    start = time.perf_counter()
    rows = conn.execute(sql, params).fetchall()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms, len(rows)


def run_benchmark_case(
    conn: sqlite3.Connection,
    case: BenchmarkCase,
    *,
    repeats: int = 3,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be positive")

    plan = _plan_rows(conn, case.sql, case.params)
    timings: list[float] = []
    row_count = 0

    for _ in range(repeats):
        elapsed_ms, row_count = _execute_once(conn, case.sql, case.params)
        timings.append(elapsed_ms)

    plan_text = "\n".join(plan)
    return {
        "name": case.name,
        "sql": _clean_sql(case.sql),
        "params": list(case.params),
        "row_count": row_count,
        "repeats": repeats,
        "min_ms": round(min(timings), 3),
        "median_ms": round(statistics.median(timings), 3),
        "max_ms": round(max(timings), 3),
        "uses_temp_btree": "USE TEMP B-TREE" in plan_text.upper(),
        "plan": plan,
    }


def run_benchmark(
    db_path: str,
    cases: Iterable[BenchmarkCase],
    *,
    repeats: int = 3,
) -> list[dict[str, Any]]:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [run_benchmark_case(conn, case, repeats=repeats) for case in cases]
    finally:
        conn.close()


def _default_db_path() -> str:
    return DB_MAPPING["village"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect EXPLAIN QUERY PLAN and timing for VillagesML ngram query shapes."
    )
    parser.add_argument("--db", default=_default_db_path(), help="Path to villages.db")
    parser.add_argument("--region", required=True, help="Existing region name, e.g. 太平镇")
    parser.add_argument("--ngram", required=True, help="Existing ngram, e.g. 新村")
    parser.add_argument("--n", type=int, default=2, help="N-gram size")
    parser.add_argument("--position", default="all", help="N-gram position")
    parser.add_argument("--level", default="township", choices=("city", "county", "township"))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", choices=("json", "text"), default="text")
    args = parser.parse_args()

    cases = build_default_cases(
        region=args.region,
        ngram=args.ngram,
        n=args.n,
        position=args.position,
        level=args.level,
        limit=args.limit,
    )
    results = run_benchmark(str(Path(args.db)), cases, repeats=args.repeats)

    if args.output == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    for result in results:
        marker = "TEMP-BTREE" if result["uses_temp_btree"] else "indexed/sorted"
        print(f"[{marker}] {result['name']}: median={result['median_ms']}ms rows={result['row_count']}")
        for row in result["plan"]:
            print(f"  {row}")


if __name__ == "__main__":
    main()
