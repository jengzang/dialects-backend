from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.common.path import DIALECTS_DB_USER, QUERY_DB_USER  # noqa: E402
from app.tools.cluster.service.resolver_service import (  # noqa: E402
    resolve_cluster_job_snapshot,
    resolve_locations,
)
from app.tools.cluster.service.staged_session_service import (  # noqa: E402
    build_staged_preview_payload,
    get_staged_result_by_hash,
    materialize_distance_artifact,
    materialize_prepare_artifact,
    materialize_result_artifact,
)


def _pick_locations(limit: int = 12) -> list[str]:
    conn = sqlite3.connect(DIALECTS_DB_USER)
    try:
        rows = conn.execute(
            """
            SELECT 簡稱
            FROM dialects
            GROUP BY 簡稱
            ORDER BY COUNT(*) DESC, 簡稱
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    candidates = [row[0] for row in rows]
    resolved = resolve_locations(
        locations=candidates,
        regions=[],
        region_mode="yindian",
        query_db=QUERY_DB_USER,
        include_special_locations=False,
        requested_locations_raw=candidates,
        requested_regions_raw=[],
    )
    matched = resolved["matched_locations"]
    if len(matched) < 3:
        raise RuntimeError("cluster staged smoke 未找到足够的有效地点")
    return matched[:3]


def _pick_common_chars(locations: list[str], limit: int = 6) -> list[str]:
    placeholders = ",".join("?" for _ in locations)
    conn = sqlite3.connect(DIALECTS_DB_USER)
    try:
        rows = conn.execute(
            f"""
            SELECT 漢字
            FROM dialects
            WHERE 簡稱 IN ({placeholders})
            GROUP BY 漢字
            HAVING COUNT(DISTINCT 簡稱) = ?
            ORDER BY 漢字
            LIMIT ?
            """,
            [*locations, len(locations), limit],
        ).fetchall()
    finally:
        conn.close()

    chars = [row[0] for row in rows]
    if len(chars) < 4:
        raise RuntimeError("cluster staged smoke 未找到足够的共现汉字")
    return chars


async def _build_snapshot() -> dict:
    locations = _pick_locations()
    chars = _pick_common_chars(locations)
    payload = {
        "groups": [
            {
                "label": "g1",
                "source_mode": "custom",
                "resolved_chars": chars[:3],
                "compare_dimension": "final",
            },
            {
                "label": "g2",
                "source_mode": "custom",
                "resolved_chars": chars[3:6],
                "compare_dimension": "final",
            },
        ],
        "locations": locations,
        "regions": [],
        "region_mode": "yindian",
        "include_special_locations": False,
        "requested_locations_raw": locations,
        "requested_regions_raw": [],
    }
    return await resolve_cluster_job_snapshot(payload, query_db=QUERY_DB_USER)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    snapshot = asyncio.run(_build_snapshot())
    preview = build_staged_preview_payload(
        snapshot,
        dialects_db=DIALECTS_DB_USER,
        query_db=QUERY_DB_USER,
    )
    prepare_hash = str(preview["prepare_hash"])
    _assert(bool(prepare_hash), "preview should return prepare_hash")

    prepare_first = materialize_prepare_artifact(prepare_hash)
    _assert(prepare_first["prepare_hash"] == prepare_hash, "prepare_hash should be stable")

    prepare_second = materialize_prepare_artifact(prepare_hash)
    _assert(
        bool(prepare_second.get("cache_hit")),
        "second prepare should hit cache or disk artifact",
    )

    distance_first = materialize_distance_artifact(
        prepare_hash,
        phoneme_mode="intra_group",
    )
    distance_hash = str(distance_first["distance_hash"])
    _assert(bool(distance_hash), "distance should return distance_hash")

    distance_second = materialize_distance_artifact(
        prepare_hash,
        phoneme_mode="intra_group",
    )
    _assert(
        bool(distance_second.get("cache_hit")),
        "second distance should hit cache or disk artifact",
    )

    clustering = {
        "algorithm": "agglomerative",
        "n_clusters": 2,
        "linkage": "average",
        "random_state": 42,
    }
    result_first = materialize_result_artifact(distance_hash, clustering)
    result_hash = str(result_first["result_hash"])
    _assert(bool(result_hash), "cluster should return result_hash")

    result_second = materialize_result_artifact(distance_hash, clustering)
    _assert(
        bool(result_second.get("cache_hit")),
        "second cluster should hit cache or disk artifact",
    )

    result_payload = get_staged_result_by_hash(result_hash)
    summary = result_payload.get("summary") or {}
    _assert(summary.get("cluster_count") is not None, "result payload missing summary")
    print("cluster_staged_token_smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
