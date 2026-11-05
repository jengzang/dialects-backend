"""Serial, local, read-only benchmark. No Redis/network/server or DB copying."""
import argparse
import json
import os
from pathlib import Path
import resource
import statistics
import sys
import time
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class MemoryRedis:
    """Measures serialization/lookup overhead only; does not simulate network latency."""
    def __init__(self):
        self.values = {}
    def get(self, key):
        return self.values.get(key)
    def set(self, key, value):
        self.values[key] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("query", "dialects", "yubao", "village"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--runs", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    os.environ["_RUN_TYPE"] = "MINE"  # Never connect to configured production Redis.
    from app.common.path import DB_MAPPING
    from app.common import fixed_default_cache as cache
    from app.lifecycle.fixed_cache_warmup import default_entries, _readonly, _run
    from app.service.fixed_defaults import load_on_connection
    for name in ("query", "dialects", "yubao", "village"):
        path = getattr(args, name).resolve(strict=True)
        DB_MAPPING[name] = str(path)
    rows = []
    expected = {}
    for slot, path, _ in default_entries():
        client = MemoryRedis()
        sql_calls = 0
        def load():
            nonlocal sql_calls
            deadline = time.monotonic() + 30
            with _readonly(path, lambda: time.monotonic() >= deadline) as db:
                db.set_trace_callback(trace)
                return load_on_connection(slot, db)
        def trace(sql):
            nonlocal sql_calls
            if sql.lstrip().upper().startswith(("SELECT", "WITH", "PRAGMA")):
                sql_calls += 1
        def timed(func):
            t0 = time.perf_counter()
            result = func()
            return result, (time.perf_counter() - t0) * 1000
        try:
            raw_times = []
            for _ in range(args.runs):
                result, elapsed = timed(load)
                raw_times.append(elapsed)
            expected[slot] = result
            raw_sql = sql_calls
            _, build_ms = timed(lambda: cache.call(slot, path, load, client=client))
            before = sql_calls
            hit_times = [timed(lambda: cache.call(slot, path, load, client=client))[1] for _ in range(args.runs)]
            rows.append({
                "slot": slot, "path": path,
                "raw_ms": raw_times, "raw_median_ms": statistics.median(raw_times),
                "build_ms": build_ms, "hit_ms": hit_times,
                "hit_median_ms": statistics.median(hit_times),
                "raw_sql_statements": raw_sql, "hit_sql_statements": sql_calls - before,
                "response_bytes": len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()),
                "stored_envelope_bytes": sum(len(v.encode()) for v in client.values.values()),
            })
        except Exception as exc:
            rows.append({"slot": slot, "error": str(exc)})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    startup_client = MemoryRedis()
    startup_started = time.perf_counter()
    _run(None, startup_client, threading.Event())
    startup_ms = (time.perf_counter() - startup_started) * 1000
    startup_equivalent = len(startup_client.values) == 6 and all(
        json.loads(startup_client.values[cache.key(slot)])["payload"] == value
        for slot, value in expected.items())
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_mib = peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024
    report = {"backend": "in-process Redis test double, no network or MEMORY USAGE",
              "runs": args.runs, "peak_process_rss_mib": peak_mib,
              "startup_warmup_ms": startup_ms, "startup_warmed_slots": len(startup_client.values),
              "startup_payload_bytes": sum(len(v.encode()) for v in startup_client.values.values()),
              "startup_equivalent_to_foreground": startup_equivalent,
              "results": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return int(any("error" in row for row in rows) or not startup_equivalent)


if __name__ == "__main__":
    raise SystemExit(main())
