from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_cluster_app


async def _fake_resolve_snapshot(payload_dict, query_db):
    return {
        "groups": [{"resolved_chars": ["字"], "compare_dimension": "initial"}],
        "location_resolution": {"matched_locations": ["A"], "matched_location_count": 1},
    }


def _build_client_and_routes():
    routes_mod = __import__("app.tools.cluster.routes", fromlist=["x"])
    client = TestClient(create_cluster_app())
    return client, routes_mod


def test_cluster_job_route_enqueues_instead_of_background(monkeypatch):
    client, routes_mod = _build_client_and_routes()
    enqueued = []

    monkeypatch.setattr("app.tools.cluster.routes._resolve_snapshot_from_payload", _fake_resolve_snapshot)
    monkeypatch.setattr(routes_mod, "enqueue_job", lambda **kwargs: enqueued.append(kwargs))

    routes_mod._cluster_service = lambda: {
        "build_task_summary": lambda snapshot, result=None: {"ok": True},
        "get_cluster_result": lambda task_id: None,
        "get_task_status_payload": lambda task_id: None,
        "resolve_cluster_job_snapshot": lambda payload_dict, query_db: {
            "groups": [{"resolved_chars": ["字"], "compare_dimension": "initial"}],
            "location_resolution": {"matched_locations": ["A"], "matched_location_count": 1},
        },
        "run_cluster_job": lambda *args, **kwargs: None,
    }
    routes_mod._cluster_cache_service = lambda: {
        "annotate_cluster_result_cache": lambda cached_result, **kwargs: cached_result,
        "build_cluster_job_hash": lambda snapshot, dialects_db, query_db: "hash1",
        "clear_inflight_task_id": lambda job_hash, task_id=None: None,
        "get_cached_cluster_result": lambda job_hash: None,
        "get_inflight_task_id": lambda job_hash: None,
        "set_inflight_task_id": lambda job_hash, task_id: None,
    }

    class FakeTaskManager:
        def create_task(self, tool_name, initial_data):
            return "cluster_task_1"

        def update_task(self, *args, **kwargs):
            return None

    routes_mod.task_manager = FakeTaskManager()

    payload = {
        "groups": [
            {
                "source_mode": "custom",
                "custom_chars": ["字"],
                "compare_dimension": "initial",
            }
        ],
        "locations": ["广州"],
        "regions": [],
        "clustering": {
            "algorithm": "kmeans",
            "n_clusters": 3,
            "phoneme_mode": "intra_group",
        },
    }
    response = client.post("/api/tools/cluster/jobs", json=payload)
    assert response.status_code == 200
    assert enqueued == [
        {
            "job_type": "cluster_job",
            "task_id": "cluster_task_1",
            "payload": {
                "dialects_db": "/Users/jengzang/CodeProject/dialects/dialects-backend/data/dialects_user.db",
                "query_db": "/Users/jengzang/CodeProject/dialects/dialects-backend/data/query_user.db",
            },
        }
    ]


def test_staged_prepare_route_enqueues_prepare_job(monkeypatch):
    client, routes_mod = _build_client_and_routes()
    enqueued = []
    monkeypatch.setattr(routes_mod, "enqueue_job", lambda **kwargs: enqueued.append(kwargs))
    routes_mod._cluster_staged_service = lambda: {
        "start_prepare_task": lambda prepare_hash: (
            True,
            {
                "task_id": "prepare_task_1",
                "stage": "prepare",
                "status": "pending",
                "progress": 0.0,
                "message": "prepare queued",
                "prepare_hash": prepare_hash,
                "cache_hit": False,
                "cache_source": "none",
            },
        )
    }

    response = client.post("/api/tools/cluster/staged/prepare", json={"prepare_hash": "prep_1"})
    assert response.status_code == 200
    assert enqueued == [
        {
            "job_type": "staged_prepare",
            "task_id": "prepare_task_1",
            "payload": {},
        }
    ]


def test_staged_distance_route_enqueues_distance_job(monkeypatch):
    client, routes_mod = _build_client_and_routes()
    enqueued = []
    monkeypatch.setattr(routes_mod, "enqueue_job", lambda **kwargs: enqueued.append(kwargs))
    routes_mod._cluster_staged_service = lambda: {
        "start_distance_task": lambda prepare_hash, phoneme_mode: (
            True,
            {
                "task_id": "distance_task_1",
                "stage": "distance",
                "status": "pending",
                "progress": 0.0,
                "message": "distance queued",
                "prepare_hash": prepare_hash,
                "distance_hash": "dist_1",
                "cache_hit": False,
                "cache_source": "none",
            },
        )
    }

    response = client.post(
        "/api/tools/cluster/staged/distances",
        json={"prepare_hash": "prep_1", "phoneme_mode": "intra_group"},
    )
    assert response.status_code == 200
    assert enqueued == [
        {
            "job_type": "staged_distance",
            "task_id": "distance_task_1",
            "payload": {"phoneme_mode": "intra_group"},
        }
    ]


def test_staged_cluster_route_enqueues_cluster_job(monkeypatch):
    client, routes_mod = _build_client_and_routes()
    enqueued = []
    monkeypatch.setattr(routes_mod, "enqueue_job", lambda **kwargs: enqueued.append(kwargs))
    routes_mod._cluster_staged_service = lambda: {
        "start_cluster_task": lambda distance_hash, clustering_config: (
            True,
            {
                "task_id": "cluster_stage_task_1",
                "stage": "cluster",
                "status": "pending",
                "progress": 0.0,
                "message": "cluster queued",
                "prepare_hash": "prep_1",
                "distance_hash": distance_hash,
                "result_hash": "result_1",
                "cache_hit": False,
                "cache_source": "none",
            },
        )
    }

    response = client.post(
        "/api/tools/cluster/staged/clusters",
        json={
            "distance_hash": "dist_1",
            "clustering": {"algorithm": "kmeans", "n_clusters": 3},
        },
    )
    assert response.status_code == 200
    assert enqueued == [
        {
            "job_type": "staged_cluster",
            "task_id": "cluster_stage_task_1",
            "payload": {
                "distance_hash": "dist_1",
                "clustering_config": {"algorithm": "kmeans", "n_clusters": 3, "linkage": "average", "eps": 0.5, "min_samples": 5, "random_state": 42},
            },
        }
    ]
