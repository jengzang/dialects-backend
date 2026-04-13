"""
Dialect clustering tool routes.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from app.service.geo.match_input_tip import match_locations_batch_all
from app.sql.db_selector import get_dialects_db, get_query_db
from app.tools.task_manager import task_manager

from .service.cluster_service import (
    build_task_summary,
    get_cluster_result,
    get_task_status_payload,
    resolve_cluster_job_snapshot,
    run_cluster_job,
)
from .service.cache_service import (
    annotate_cluster_result_cache,
    build_cluster_job_hash,
    clear_inflight_task_id,
    get_cached_cluster_result,
    get_inflight_task_id,
    set_inflight_task_id,
)
from .service.task_service import write_result
from .schemas import (
    ClusterJobCreateRequest,
    ClusterJobCreateResponse,
    ClusterJobStatusResponse,
)

router = APIRouter()


@router.post("/jobs", response_model=ClusterJobCreateResponse)
async def create_cluster_job(
    payload: ClusterJobCreateRequest,
    background_tasks: BackgroundTasks,
    query_db: str = Depends(get_query_db),
    dialects_db: str = Depends(get_dialects_db),
):
    payload_dict = payload.model_dump(mode="json")
    payload_dict["requested_locations_raw"] = list(payload.locations or [])
    payload_dict["requested_regions_raw"] = list(payload.regions or [])

    try:
        processed_locations = await run_in_threadpool(
            match_locations_batch_all,
            payload.locations or [],
            True,
            True,
            query_db,
            None,
            None,
        )
        payload_dict["locations"] = processed_locations
        snapshot = await resolve_cluster_job_snapshot(
            payload_dict,
            query_db=query_db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"解析聚类请求失败: {exc}")

    job_hash = build_cluster_job_hash(snapshot, dialects_db, query_db)
    cached_result = get_cached_cluster_result(job_hash)
    if cached_result is not None:
        task_id = task_manager.create_task(
            "cluster",
            {
                "snapshot": snapshot,
                "summary": build_task_summary(snapshot),
                "job_hash": job_hash,
                "query_db": query_db,
            },
        )
        result = annotate_cluster_result_cache(
            cached_result,
            job_hash=job_hash,
            cache_hit=True,
            cache_source="result",
        )
        result_path = write_result(task_id, result)
        summary = build_task_summary(snapshot, result=result)
        task_manager.update_task(
            task_id,
            status="completed",
            progress=100.0,
            message="聚类结果命中缓存",
            data={
                "result_path": str(result_path),
                "summary": summary,
                "job_hash": job_hash,
                "query_db": query_db,
                "execution_time_ms": (result.get("metadata") or {}).get("execution_time_ms"),
                "performance": (result.get("metadata") or {}).get("performance"),
            },
        )
        return ClusterJobCreateResponse(
            task_id=task_id,
            status="completed",
            progress=100.0,
            message="聚类结果命中缓存",
            summary=summary,
        )

    inflight_task_id = get_inflight_task_id(job_hash)
    if inflight_task_id:
        inflight_payload = get_task_status_payload(inflight_task_id)
        if inflight_payload and inflight_payload.get("status") in {"pending", "processing"}:
            return ClusterJobCreateResponse(
                task_id=inflight_task_id,
                status=str(inflight_payload.get("status")),
                progress=float(inflight_payload.get("progress", 0.0)),
                message=str(inflight_payload.get("message") or ""),
                summary=inflight_payload.get("summary"),
            )
        clear_inflight_task_id(job_hash, task_id=inflight_task_id)

    task_id = task_manager.create_task(
        "cluster",
        {
            "snapshot": snapshot,
            "summary": build_task_summary(snapshot),
            "job_hash": job_hash,
            "query_db": query_db,
        },
    )
    set_inflight_task_id(job_hash, task_id)
    task_manager.update_task(
        task_id,
        progress=0.0,
        message="聚类任务已创建，等待执行",
    )

    background_tasks.add_task(run_cluster_job, task_id, dialects_db, query_db)

    return ClusterJobCreateResponse(
        task_id=task_id,
        status="pending",
        progress=0.0,
        message="聚类任务已创建",
        summary=build_task_summary(snapshot),
    )


@router.get("/jobs/{task_id}", response_model=ClusterJobStatusResponse)
async def get_cluster_job_status(task_id: str):
    payload = get_task_status_payload(task_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ClusterJobStatusResponse(**payload)


@router.get("/jobs/{task_id}/result")
async def get_cluster_job_result(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    result = get_cluster_result(task_id)
    if result is None:
        raise HTTPException(status_code=400, detail="任务尚未完成或结果不存在")
    return result


@router.delete("/jobs/{task_id}")
async def delete_cluster_job(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task_manager.delete_task(task_id)
    return {
        "task_id": task_id,
        "status": "deleted",
        "message": "聚类任务已删除",
    }
