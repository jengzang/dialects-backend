"""Compare fresh vs retained read-only SQLite connections on explicit local files."""
import argparse
import gc
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def rss_kib():
    if sys.platform.startswith("linux"):
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(os.getpid())], text=True).strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--strategy", choices=["fresh-2000", "retained-2000", "retained-16000"], required=True)
    parser.add_argument("--runs", type=int, choices=range(1, 6), default=5)
    args = parser.parse_args()
    os.environ["_RUN_TYPE"] = "MINE"
    from app.common.path import DB_MAPPING
    from app.lifecycle.fixed_cache_warmup import default_entries
    from app.service.fixed_defaults import load_on_connection, readonly
    # Resolve exact input files; never create/copy them or use writable connections.
    for key, name in [("query", "query_user.db"), ("dialects", "dialects_user.db"),
                      ("yubao", "yubao.db"), ("village", "villages.db")]:
        DB_MAPPING[key] = str((args.data_dir / name).resolve(strict=True))
    # Import the same loader modules in every child before taking the RSS baseline.
    from app.sql import sql_routes
    from app.service.yubao import service
    from app.villagesML.metadata import stats
    from app.villagesML import statistics as ngram_stats
    gc.collect()
    baseline = rss_kib()
    retained, results = {}, []
    cache_kib = 16000 if args.strategy == "retained-16000" else 2000
    try:
        for slot, path, _ in default_entries():
            elapsed = []
            for _ in range(args.runs):
                started = time.perf_counter()
                if args.strategy.startswith("retained"):
                    if path not in retained:
                        context = readonly(path)
                        conn = context.__enter__()
                        retained[path] = (context, conn)
                        conn.execute(f"PRAGMA cache_size=-{cache_kib}")
                    result = load_on_connection(slot, retained[path][1])
                else:
                    with readonly(path) as conn:
                        result = load_on_connection(slot, conn)
                elapsed.append((time.perf_counter() - started) * 1000)
                del result
            results.append({"slot": slot, "ms": elapsed, "median_ms": statistics.median(elapsed)})
        gc.collect()
        idle = rss_kib()
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_mib = peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024
        print(json.dumps({"strategy": args.strategy, "rss_baseline_mib": baseline / 1024,
                          "rss_idle_mib": idle / 1024, "rss_delta_mib": (idle - baseline) / 1024,
                          "peak_rss_mib": peak_mib, "retained_connections": len(retained),
                          "results": results}, ensure_ascii=False), flush=True)
    finally:
        for context, _ in retained.values():
            context.__exit__(None, None, None)


if __name__ == "__main__":
    main()
