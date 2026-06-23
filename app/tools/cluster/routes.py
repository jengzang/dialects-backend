"""
cluster HTTP 路由入口。

这一层不参与具体音系计算，主要负责：
- 请求参数与依赖注入；
- 创建后台任务；
- 结果缓存命中与 inflight 去重；
- 对外暴露任务状态、结果和删除接口。
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from app.service.geo.match_input_tip import match_locations_batch_all
from app.sql.db_selector import get_dialects_db, get_query_db
from app.tools.task_manager import task_manager

from .schemas import (
    ClusterStageClusterRequest,
    ClusterStageDistanceRequest,
    ClusterStagePrepareRequest,
    ClusterStagePreviewRequest,
    ClusterStagePreviewResponse,
    ClusterStageTaskResponse,
    ClusterJobCreateRequest,
    ClusterJobCreateResponse,
    ClusterJobStatusResponse,
)

router = APIRouter()


def _cluster_service():
    from .service.cluster_service import (
        build_task_summary,
        get_cluster_result,
        get_task_status_payload,
        resolve_cluster_job_snapshot,
        run_cluster_job,
    )
    return {
        "build_task_summary": build_task_summary,
        "get_cluster_result": get_cluster_result,
        "get_task_status_payload": get_task_status_payload,
        "resolve_cluster_job_snapshot": resolve_cluster_job_snapshot,
        "run_cluster_job": run_cluster_job,
    }


def _cluster_cache_service():
    from .service.cache_service import (
        annotate_cluster_result_cache,
        build_cluster_job_hash,
        clear_inflight_task_id,
        get_cached_cluster_result,
        get_inflight_task_id,
        set_inflight_task_id,
    )
    return {
        "annotate_cluster_result_cache": annotate_cluster_result_cache,
        "build_cluster_job_hash": build_cluster_job_hash,
        "clear_inflight_task_id": clear_inflight_task_id,
        "get_cached_cluster_result": get_cached_cluster_result,
        "get_inflight_task_id": get_inflight_task_id,
        "set_inflight_task_id": set_inflight_task_id,
    }


def _cluster_staged_service():
    from .service.staged_session_service import (
        ClusterStageConflictError,
        ClusterStageNotFoundError,
        ClusterStageValidationError,
        build_staged_preview_payload,
        get_staged_result_by_hash,
        run_cluster_task,
        run_distance_task,
        run_prepare_task,
        start_cluster_task,
        start_distance_task,
        start_prepare_task,
    )
    return {
        "ClusterStageConflictError": ClusterStageConflictError,
        "ClusterStageNotFoundError": ClusterStageNotFoundError,
        "ClusterStageValidationError": ClusterStageValidationError,
        "build_staged_preview_payload": build_staged_preview_payload,
        "get_staged_result_by_hash": get_staged_result_by_hash,
        "run_cluster_task": run_cluster_task,
        "run_distance_task": run_distance_task,
        "run_prepare_task": run_prepare_task,
        "start_cluster_task": start_cluster_task,
        "start_distance_task": start_distance_task,
        "start_prepare_task": start_prepare_task,
    }


def _cluster_task_service():
    from .service.task_service import touch_cluster_task_cleanup, write_result
    return {
        "touch_cluster_task_cleanup": touch_cluster_task_cleanup,
        "write_result": write_result,
    }


def _raise_stage_http_error(exc: Exception) -> None:
    staged = _cluster_staged_service()
    if isinstance(exc, staged["ClusterStageNotFoundError"]):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, staged["ClusterStageConflictError"]):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, staged["ClusterStageValidationError"]):
        raise HTTPException(status_code=422, detail=str(exc))
    raise HTTPException(status_code=500, detail=f"staged cluster 请求失败: {exc}")


async def _resolve_snapshot_from_payload(
    payload_dict: Dict[str, Any],
    *,
    query_db: str,
) -> Dict[str, Any]:
    cluster_service = _cluster_service()
    payload_dict["requested_locations_raw"] = list(payload_dict.get("locations") or [])
    payload_dict["requested_regions_raw"] = list(payload_dict.get("regions") or [])
    processed_locations = await run_in_threadpool(
        match_locations_batch_all,
        payload_dict.get("locations") or [],
        True,
        True,
        query_db,
        None,
        None,
    )
    payload_dict["locations"] = processed_locations
    return await cluster_service["resolve_cluster_job_snapshot"](
        payload_dict,
        query_db=query_db,
    )


@router.post("/jobs", response_model=ClusterJobCreateResponse)
async def create_cluster_job(
    payload: ClusterJobCreateRequest,
    background_tasks: BackgroundTasks,
    query_db: str = Depends(get_query_db),
    dialects_db: str = Depends(get_dialects_db),
):
    """
    创建一个新的聚类任务。

    处理顺序是：
    1. 先把前端输入的地点做标准化匹配；
    2. 再把 group 和地点解析成稳定的 snapshot；
    3. 用 snapshot 生成 job_hash，优先查结果缓存；
    4. 若已有完全相同的任务在跑，则直接复用已有 task_id；
    5. 否则创建后台任务，由 `run_cluster_job()` 真正执行聚类。
    """
    cluster_service = _cluster_service()
    cache_service = _cluster_cache_service()
    task_service = _cluster_task_service()
    payload_dict = payload.model_dump(mode="json")

    try:
        snapshot = await _resolve_snapshot_from_payload(
            payload_dict,
            query_db=query_db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"解析聚类请求失败: {exc}")

    job_hash = cache_service["build_cluster_job_hash"](snapshot, dialects_db, query_db)
    cached_result = cache_service["get_cached_cluster_result"](job_hash)
    if cached_result is not None:
        task_id = task_manager.create_task(
            "cluster",
            {
                "snapshot": snapshot,
                "summary": cluster_service["build_task_summary"](snapshot),
                "job_hash": job_hash,
                "query_db": query_db,
            },
        )
        result = cache_service["annotate_cluster_result_cache"](
            cached_result,
            job_hash=job_hash,
            cache_hit=True,
            cache_source="result",
        )
        result_path = task_service["write_result"](task_id, result)
        summary = cluster_service["build_task_summary"](snapshot, result=result)
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
        task_service["touch_cluster_task_cleanup"](task_id, "cluster_result_cached")
        return ClusterJobCreateResponse(
            task_id=task_id,
            status="completed",
            progress=100.0,
            message="聚类结果命中缓存",
            summary=summary,
        )

    inflight_task_id = cache_service["get_inflight_task_id"](job_hash)
    if inflight_task_id:
        inflight_payload = cluster_service["get_task_status_payload"](inflight_task_id)
        if inflight_payload and inflight_payload.get("status") in {"pending", "processing"}:
            return ClusterJobCreateResponse(
                task_id=inflight_task_id,
                status=str(inflight_payload.get("status")),
                progress=float(inflight_payload.get("progress", 0.0)),
                message=str(inflight_payload.get("message") or ""),
                summary=inflight_payload.get("summary"),
            )
        cache_service["clear_inflight_task_id"](job_hash, task_id=inflight_task_id)

    task_id = task_manager.create_task(
        "cluster",
        {
            "snapshot": snapshot,
            "summary": cluster_service["build_task_summary"](snapshot),
            "job_hash": job_hash,
            "query_db": query_db,
        },
    )
    cache_service["set_inflight_task_id"](job_hash, task_id)
    task_manager.update_task(
        task_id,
        progress=0.0,
        message="聚类任务已创建，等待执行",
    )

    background_tasks.add_task(cluster_service["run_cluster_job"], task_id, dialects_db, query_db)

    return ClusterJobCreateResponse(
        task_id=task_id,
        status="pending",
        progress=0.0,
        message="聚类任务已创建",
        summary=cluster_service["build_task_summary"](snapshot),
    )


@router.post("/staged/preview", response_model=ClusterStagePreviewResponse)
async def create_cluster_staged_preview(
    payload: ClusterStagePreviewRequest,
    query_db: str = Depends(get_query_db),
    dialects_db: str = Depends(get_dialects_db),
):
    """解析输入并返回 preview + prepare_hash。"""
    staged_service = _cluster_staged_service()
    payload_dict = payload.model_dump(mode="json")
    try:
        snapshot = await _resolve_snapshot_from_payload(
            payload_dict,
            query_db=query_db,
        )
        return staged_service["build_staged_preview_payload"](
            snapshot,
            query_db=query_db,
            dialects_db=dialects_db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        _raise_stage_http_error(exc)


@router.post("/staged/prepare", response_model=ClusterStageTaskResponse)
async def start_cluster_staged_prepare(
    payload: ClusterStagePrepareRequest,
    background_tasks: BackgroundTasks,
):
    """启动或复用 prepare 阶段。"""
    staged_service = _cluster_staged_service()
    try:
        should_enqueue, response_payload = staged_service["start_prepare_task"](payload.prepare_hash)
        if should_enqueue:
            background_tasks.add_task(staged_service["run_prepare_task"], response_payload["task_id"])
        return response_payload
    except Exception as exc:
        _raise_stage_http_error(exc)


@router.post("/staged/distances", response_model=ClusterStageTaskResponse)
async def start_cluster_staged_distance(
    payload: ClusterStageDistanceRequest,
    background_tasks: BackgroundTasks,
):
    """启动或复用某个 phoneme_mode 的 distance 阶段。"""
    staged_service = _cluster_staged_service()
    try:
        should_enqueue, response_payload = staged_service["start_distance_task"](
            payload.prepare_hash,
            phoneme_mode=payload.phoneme_mode,
        )
        if should_enqueue:
            background_tasks.add_task(
                staged_service["run_distance_task"],
                response_payload["task_id"],
            )
        return response_payload
    except Exception as exc:
        _raise_stage_http_error(exc)


@router.post("/staged/clusters", response_model=ClusterStageTaskResponse)
async def start_cluster_staged_cluster(
    payload: ClusterStageClusterRequest,
    background_tasks: BackgroundTasks,
):
    """启动或复用 cluster 阶段。"""
    staged_service = _cluster_staged_service()
    try:
        should_enqueue, response_payload = staged_service["start_cluster_task"](
            payload.prepare_hash,
            payload.phoneme_modes,
            payload.cluster_params,
        )
        if should_enqueue:
            background_tasks.add_task(staged_service["run_cluster_task"], response_payload["task_id"])
        return response_payload
    except Exception as exc:
        _raise_stage_http_error(exc)


@router.get("/staged/results/{result_hash}")
async def get_cluster_staged_result(result_hash: str):
    """读取 staged 最终结果。"""
    staged_service = _cluster_staged_service()
    result = staged_service["get_staged_result_by_hash"](result_hash)
    if result is None:
        raise HTTPException(status_code=404, detail="staged result not found")
    return result


@router.get("/jobs/{task_id}", response_model=ClusterJobStatusResponse)
async def get_cluster_job_status(task_id: str):
    """查询聚类任务状态。"""
    cluster_service = _cluster_service()
    payload = cluster_service["get_task_status_payload"](task_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ClusterJobStatusResponse(**payload)


@router.get("/jobs/{task_id}/result")
async def get_cluster_job_result(task_id: str):
    """读取聚类任务结果。"""
    cluster_service = _cluster_service()
    result = cluster_service["get_cluster_result"](task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="聚类结果不存在")
    return result


@router.delete("/jobs/{task_id}")
async def delete_cluster_job(task_id: str):
    """删除聚类任务及其结果缓存。"""
    task_service = _cluster_task_service()
    task_manager.delete_task(task_id)
    task_service["touch_cluster_task_cleanup"](task_id, "cluster_job_deleted")
    return {"success": True, "task_id": task_id}
