from __future__ import annotations

import argparse
import sqlite3
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "dialects_user.db"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_cluster_modules():
    from app.tools.cluster.service.cluster_service import build_cluster_result
    from app.tools.cluster.service.loader_service import load_dialect_rows

    return build_cluster_result, load_dialect_rows


def _sample_values(
    db_path: Path,
    *,
    location_limit: int,
    char_limit: int,
) -> tuple[List[str], List[str]]:
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        locations = [
            row[0]
            for row in cursor.execute(
                "SELECT DISTINCT 簡稱 FROM dialects ORDER BY 簡稱 LIMIT ?",
                (location_limit,),
            ).fetchall()
        ]
        chars = [
            row[0]
            for row in cursor.execute(
                "SELECT DISTINCT 漢字 FROM dialects ORDER BY 漢字 LIMIT ?",
                (char_limit,),
            ).fetchall()
        ]
        return locations, chars
    finally:
        conn.close()


def _build_baseline_rows(
    db_path: Path,
    locations: Sequence[str],
    chars: Sequence[str],
) -> Dict[str, Dict[str, Dict[str, set[str]]]]:
    data: Dict[str, Dict[str, Dict[str, set[str]]]] = {}
    if not locations or not chars:
        return data

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        loc_placeholders = ",".join("?" * len(locations))
        char_placeholders = ",".join("?" * len(chars))
        query = f"""
            SELECT 簡稱, 漢字, 聲母, 韻母, 聲調
            FROM dialects
            WHERE 簡稱 IN ({loc_placeholders})
              AND 漢字 IN ({char_placeholders})
        """
        for location, char, initial, final, tone in cursor.execute(
            query,
            list(locations) + list(chars),
        ).fetchall():
            char_map = data.setdefault(location, {}).setdefault(
                char,
                {"initial": set(), "final": set(), "tone": set()},
            )
            if initial:
                char_map["initial"].add(str(initial).strip())
            if final:
                char_map["final"].add(str(final).strip())
            if tone:
                char_map["tone"].add(str(tone).strip())
        return data
    finally:
        conn.close()


def _project_dimensions(
    baseline: Dict[str, Dict[str, Dict[str, set[str]]]],
    requested_dimensions: Iterable[str],
) -> Dict[str, Dict[str, Dict[str, set[str]]]]:
    requested = set(requested_dimensions)
    projected: Dict[str, Dict[str, Dict[str, set[str]]]] = {}
    for location, char_data in baseline.items():
        projected[location] = {}
        for char, dimension_data in char_data.items():
            projected[location][char] = {
                "initial": set(dimension_data["initial"]) if "initial" in requested else set(),
                "final": set(dimension_data["final"]) if "final" in requested else set(),
                "tone": set(dimension_data["tone"]) if "tone" in requested else set(),
            }
    return projected


def _normalize_nested_sets(
    data: Dict[str, Dict[str, Dict[str, set[str]]]],
    *,
    locations: Sequence[str],
    chars: Sequence[str],
) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
    normalized: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
    for location in locations:
        normalized[location] = {}
        location_data = data.get(location, {})
        for char in chars:
            dimension_data = location_data.get(
                char,
                {"initial": set(), "final": set(), "tone": set()},
            )
            normalized[location][char] = {
                "initial": sorted(dimension_data.get("initial", set())),
                "final": sorted(dimension_data.get("final", set())),
                "tone": sorted(dimension_data.get("tone", set())),
            }
    return normalized


def _run_sql_benchmark(
    db_path: Path,
    locations: Sequence[str],
    chars: Sequence[str],
    *,
    repeats: int,
) -> Dict[str, object]:
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        loc_placeholders = ",".join("?" * len(locations))
        char_placeholders = ",".join("?" * len(chars))
        params = list(locations) + list(chars)

        query_in = f"""
            SELECT 簡稱, 漢字, 聲母, 韻母, 聲調
            FROM dialects
            WHERE 簡稱 IN ({loc_placeholders})
              AND 漢字 IN ({char_placeholders})
        """

        query_join = """
            SELECT d.簡稱, d.漢字, d.聲母, d.韻母, d.聲調
            FROM dialects AS d
            INNER JOIN temp_cluster_locations AS l
                ON l.value = d.簡稱
            INNER JOIN temp_cluster_chars AS c
                ON c.value = d.漢字
        """

        query_in_select = """
            SELECT 簡稱, 漢字, 聲母, 韻母, 聲調
            FROM dialects
            WHERE 簡稱 IN (SELECT value FROM temp_cluster_locations)
              AND 漢字 IN (SELECT value FROM temp_cluster_chars)
        """

        def reset_temp_tables():
            cursor.execute("DROP TABLE IF EXISTS temp_cluster_locations")
            cursor.execute("DROP TABLE IF EXISTS temp_cluster_chars")
            cursor.execute(
                "CREATE TEMP TABLE temp_cluster_locations(value TEXT PRIMARY KEY)"
            )
            cursor.execute(
                "CREATE TEMP TABLE temp_cluster_chars(value TEXT PRIMARY KEY)"
            )
            cursor.executemany(
                "INSERT OR IGNORE INTO temp_cluster_locations(value) VALUES (?)",
                [(value,) for value in locations],
            )
            cursor.executemany(
                "INSERT OR IGNORE INTO temp_cluster_chars(value) VALUES (?)",
                [(value,) for value in chars],
            )

        def explain(query: str, query_params: Sequence[str]) -> List[str]:
            return [
                row[-1]
                for row in cursor.execute(
                    "EXPLAIN QUERY PLAN " + query,
                    list(query_params),
                ).fetchall()
            ]

        def explain_temp(query: str) -> List[str]:
            reset_temp_tables()
            return [row[-1] for row in cursor.execute("EXPLAIN QUERY PLAN " + query).fetchall()]

        def bench_plain(query: str, query_params: Sequence[str]) -> tuple[int, List[float]]:
            elapsed_ms: List[float] = []
            row_count = 0
            for _ in range(repeats):
                started = time.perf_counter()
                rows = cursor.execute(query, list(query_params)).fetchall()
                elapsed_ms.append((time.perf_counter() - started) * 1000.0)
                row_count = len(rows)
            return row_count, elapsed_ms

        def bench_temp(query: str) -> tuple[int, List[float]]:
            elapsed_ms: List[float] = []
            row_count = 0
            for _ in range(repeats):
                reset_temp_tables()
                started = time.perf_counter()
                rows = cursor.execute(query).fetchall()
                elapsed_ms.append((time.perf_counter() - started) * 1000.0)
                row_count = len(rows)
            return row_count, elapsed_ms

        rows_in, in_times = bench_plain(query_in, params)
        rows_join, join_times = bench_temp(query_join)
        rows_in_select, in_select_times = bench_temp(query_in_select)

        return {
            "plans": {
                "in": explain(query_in, params),
                "join": explain_temp(query_join),
                "in_select": explain_temp(query_in_select),
            },
            "timings_ms": {
                "in": [round(value, 2) for value in in_times],
                "join": [round(value, 2) for value in join_times],
                "in_select": [round(value, 2) for value in in_select_times],
            },
            "averages_ms": {
                "in": round(statistics.mean(in_times), 2),
                "join": round(statistics.mean(join_times), 2),
                "in_select": round(statistics.mean(in_select_times), 2),
            },
            "row_counts": {
                "in": rows_in,
                "join": rows_join,
                "in_select": rows_in_select,
            },
        }
    finally:
        conn.close()


def _build_snapshot(
    *,
    locations: Sequence[str],
    groups: List[Dict[str, object]],
    phoneme_mode: str,
) -> Dict[str, object]:
    return {
        "groups": groups,
        "clustering": {
            "algorithm": "agglomerative",
            "phoneme_mode": phoneme_mode,
            "n_clusters": 2,
        },
        "location_resolution": {
            "requested_locations": list(locations),
            "requested_regions": [],
            "region_mode": "yindian",
            "include_special_locations": False,
            "expanded_inputs": list(locations),
            "matched_locations": list(locations),
            "location_details": {},
            "matched_location_count_before_filter": len(locations),
            "filtered_special_locations": [],
            "filtered_special_location_count": 0,
            "requested_location_count": len(locations),
            "requested_region_count": 0,
            "expanded_input_count": len(locations),
            "matched_location_count": len(locations),
        },
        "performance": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Cluster loader smoke and benchmark.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB))
    parser.add_argument("--location-limit", type=int, default=50)
    parser.add_argument("--char-limit", type=int, default=200)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    db_path = Path(args.db_path)
    build_cluster_result, load_dialect_rows = _load_cluster_modules()
    locations, chars = _sample_values(
        db_path,
        location_limit=args.location_limit,
        char_limit=args.char_limit,
    )
    requested_dimensions = ["initial"]

    baseline = _build_baseline_rows(db_path, locations, chars)
    expected_projected = _project_dimensions(baseline, requested_dimensions)
    full_load_started = time.perf_counter()
    all_dimensions = load_dialect_rows(
        locations,
        chars,
        str(db_path),
        requested_dimensions=None,
    )
    full_load_elapsed_ms = round((time.perf_counter() - full_load_started) * 1000.0, 2)
    requested_load_started = time.perf_counter()
    requested_only = load_dialect_rows(
        locations,
        chars,
        str(db_path),
        requested_dimensions=requested_dimensions,
    )
    requested_load_elapsed_ms = round(
        (time.perf_counter() - requested_load_started) * 1000.0,
        2,
    )

    assert _normalize_nested_sets(
        all_dimensions,
        locations=locations,
        chars=chars,
    ) == _normalize_nested_sets(
        baseline,
        locations=locations,
        chars=chars,
    ), "full-dimension loader output diverged from baseline query"

    assert _normalize_nested_sets(
        requested_only,
        locations=locations,
        chars=chars,
    ) == _normalize_nested_sets(
        expected_projected,
        locations=locations,
        chars=chars,
    ), "requested-dimension loader output diverged from projected baseline"

    benchmark = _run_sql_benchmark(
        db_path,
        locations,
        chars,
        repeats=args.repeats,
    )

    in_select_plan = " | ".join(benchmark["plans"]["in_select"])
    assert "SCAN dialects" not in in_select_plan, benchmark["plans"]["in_select"]

    single_group = [
        {
            "label": "initial_group",
            "source_mode": "custom",
            "table_name": "characters",
            "path_strings": None,
            "column": None,
            "combine_query": False,
            "filters": None,
            "exclude_columns": None,
            "compare_dimension": "initial",
            "feature_column": "聲母",
            "group_weight": 1.0,
            "use_phonetic_values": False,
            "phonetic_value_weight": 0.2,
            "resolved_chars": chars[:12],
            "char_count": len(chars[:12]),
            "sample_chars": list(chars[:12]),
            "cache_hit": False,
            "cache_key": None,
            "resolver": "custom_chars",
            "query_labels": [],
        }
    ]
    multi_group = [
        dict(single_group[0]),
        {
            "label": "tone_group",
            "source_mode": "custom",
            "table_name": "characters",
            "path_strings": None,
            "column": None,
            "combine_query": False,
            "filters": None,
            "exclude_columns": None,
            "compare_dimension": "tone",
            "feature_column": "聲調",
            "group_weight": 1.0,
            "use_phonetic_values": False,
            "phonetic_value_weight": 0.2,
            "resolved_chars": chars[12:24],
            "char_count": len(chars[12:24]),
            "sample_chars": list(chars[12:24]),
            "cache_hit": False,
            "cache_key": None,
            "resolver": "custom_chars",
            "query_labels": [],
        },
    ]

    cluster_results = {}
    for phoneme_mode, groups in (
        ("intra_group", single_group),
        ("anchored_inventory", multi_group),
        ("shared_request_identity", multi_group),
    ):
        result = build_cluster_result(
            _build_snapshot(
                locations=locations[:6],
                groups=groups,
                phoneme_mode=phoneme_mode,
            ),
            dialects_db=str(db_path),
        )
        assert result["summary"]["effective_location_count"] >= 2, result["summary"]
        cluster_results[phoneme_mode] = {
            "cluster_count": result["summary"]["cluster_count"],
            "performance": result["metadata"]["performance"],
        }

    print(
        {
            "sample_sizes": {
                "locations": len(locations),
                "chars": len(chars),
            },
            "loader_checks": {
                "input_locations": len(locations),
                "input_chars": len(chars),
                "loaded_locations_full": len(all_dimensions),
                "loaded_locations_requested": len(requested_only),
                "full_load_elapsed_ms": full_load_elapsed_ms,
                "requested_load_elapsed_ms": requested_load_elapsed_ms,
            },
            "benchmark": benchmark,
            "cluster_results": cluster_results,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
