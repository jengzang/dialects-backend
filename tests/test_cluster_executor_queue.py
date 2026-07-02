from __future__ import annotations

from app.tools.cluster.executor_queue import (
    claim_next_job,
    completed_dir,
    enqueue_job,
    failed_dir,
    mark_job_completed,
    mark_job_failed,
    pending_dir,
    processing_dir,
    requeue_processing_jobs,
)


def test_enqueue_claim_complete_cycle(tmp_path, monkeypatch):
    from app.tools import file_manager as fm_mod
    from app.tools.cluster import executor_queue as q

    fm_mod.file_manager.base_dir = tmp_path

    envelope = enqueue_job(job_type="cluster_job", task_id="cluster_1", payload={"a": 1})
    assert (pending_dir() / f"{envelope['job_id']}.json").exists()

    claimed = claim_next_job()
    assert claimed is not None
    assert claimed["job_id"] == envelope["job_id"]
    assert (processing_dir() / f"{envelope['job_id']}.json").exists()

    done = mark_job_completed(envelope["job_id"])
    assert done["status"] == "completed"
    assert (completed_dir() / f"{envelope['job_id']}.json").exists()


def test_mark_failed_cycle(tmp_path):
    from app.tools import file_manager as fm_mod

    fm_mod.file_manager.base_dir = tmp_path

    envelope = enqueue_job(job_type="cluster_job", task_id="cluster_2", payload={})
    claim_next_job()
    failed = mark_job_failed(envelope["job_id"], error="boom")
    assert failed["status"] == "failed"
    assert failed["error"] == "boom"
    assert (failed_dir() / f"{envelope['job_id']}.json").exists()


def test_requeue_processing_jobs(tmp_path):
    from app.tools import file_manager as fm_mod

    fm_mod.file_manager.base_dir = tmp_path

    envelope = enqueue_job(job_type="cluster_job", task_id="cluster_3", payload={})
    claim_next_job()
    count = requeue_processing_jobs()
    assert count == 1
    assert (pending_dir() / f"{envelope['job_id']}.json").exists()
