from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from ..run_id_manager import run_id_manager
from app.service.auth.core.dependencies import get_current_admin_user

"""
Run ID 管理 API 路由。

提供读取当前激活 run_id、列出可用 run_id、切换激活 run_id、
查询元数据以及刷新缓存的接口。
"""

router = APIRouter()


class SetActiveRunIDRequest(BaseModel):
    """设置激活 run_id 的请求体。"""

    run_id: str
    updated_by: Optional[str] = None
    notes: Optional[str] = None


@router.get("/run-ids/active")
def get_all_active_run_ids():
    """
    获取所有分析类型当前激活的 run_id。

    Returns:
        所有分析类型对应的当前激活 run_id。
    """
    try:
        result = run_id_manager.get_all_active_run_ids()
        return {
            "success": True,
            "data": result,
            "count": len(result),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/run-ids/active/{analysis_type}")
def get_active_run_id(
    analysis_type: str,  # 分析类型名称
):
    """
    获取指定分析类型当前激活的 run_id。

    Args:
        analysis_type: 分析类型名称。

    Returns:
        当前激活的 run_id 信息。
    """
    try:
        run_id = run_id_manager.get_active_run_id(analysis_type)
        return {
            "success": True,
            "analysis_type": analysis_type,
            "run_id": run_id,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/run-ids/available/{analysis_type}")
def list_available_run_ids(analysis_type: str):
    """
    列出指定分析类型下可用的 run_id。

    Args:
        analysis_type: 分析类型名称。

    Returns:
        可用 run_id 列表。
    """
    try:
        run_ids = run_id_manager.list_available_run_ids(analysis_type)
        return {
            "success": True,
            "analysis_type": analysis_type,
            "available_run_ids": run_ids,
            "count": len(run_ids),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/run-ids/active/{analysis_type}")
def set_active_run_id(
    analysis_type: str,
    request: SetActiveRunIDRequest,
    _admin=Depends(get_current_admin_user),
):
    """
    设置指定分析类型的激活 run_id。

    Args:
        analysis_type: 分析类型名称。
        request: 包含 `run_id`、`updated_by` 和 `notes` 的请求体。
        admin: 当前管理员用户。

    Returns:
        更新结果。
    """
    try:
        run_id_manager.set_active_run_id(
            analysis_type=analysis_type,
            run_id=request.run_id,
            updated_by=request.updated_by,
            notes=request.notes,
        )

        return {
            "success": True,
            "message": f"已将 {analysis_type} 的激活 run_id 更新为 {request.run_id}",
            "analysis_type": analysis_type,
            "run_id": request.run_id,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/run-ids/metadata/{run_id}")
def get_run_id_metadata(run_id: str):
    """
    获取 run_id 的元数据。

    Args:
        run_id: run_id 名称。

    Returns:
        run_id 元数据。
    """
    try:
        metadata = run_id_manager.get_run_id_metadata(run_id)
        return {
            "success": True,
            "data": metadata,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-ids/refresh")
def refresh_cache(
    _admin=Depends(get_current_admin_user),
):
    """
    刷新 run_id 缓存。

    Returns:
        刷新结果。
    """
    try:
        run_id_manager.refresh_cache()
        return {
            "success": True,
            "message": "缓存刷新成功",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
