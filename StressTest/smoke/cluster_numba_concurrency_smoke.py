from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from StressTest.smoke.cluster_distance_matrix_smoke import (  # noqa: E402
    build_mixed_dimension_fixture,
    build_single_dimension_fixture,
)
from app.tools.cluster.service.distance_service import build_total_distance_matrix  # noqa: E402


def _run_once(mode: str, fixture: str) -> float:
    if fixture == "single":
        locations, group_models, inventory_profiles, bucket_models = build_single_dimension_fixture()
    else:
        locations, group_models, inventory_profiles, bucket_models = build_mixed_dimension_fixture()
    matrix, _ = build_total_distance_matrix(
        group_models=group_models,
        locations=locations,
        phoneme_mode=mode,
        inventory_profiles=inventory_profiles,
        bucket_models=bucket_models,
    )
    return float(matrix.sum())


def main() -> None:
    parser = argparse.ArgumentParser(description="并发触发 cluster numba 距离矩阵快路径。")
    parser.add_argument(
        "--mode",
        default="intra_group",
        choices=["intra_group", "anchored_inventory", "shared_request_identity"],
    )
    parser.add_argument(
        "--fixture",
        default="single",
        choices=["single", "mixed"],
    )
    parser.add_argument("--loops", type=int, default=10)
    args = parser.parse_args()

    checksum = _run_once(args.mode, args.fixture)

    def _worker() -> None:
        for _ in range(args.loops):
            value = _run_once(args.mode, args.fixture)
            if abs(value - checksum) > 1e-9:
                raise AssertionError(f"checksum mismatch: {value} != {checksum}")

    threads = [threading.Thread(target=_worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print(
        {
            "status": "ok",
            "mode": args.mode,
            "fixture": args.fixture,
            "loops": args.loops,
            "checksum": round(checksum, 6),
        }
    )


if __name__ == "__main__":
    main()
