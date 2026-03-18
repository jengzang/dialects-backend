"""
Run_ID 绠＄悊 API 绔偣

鎻愪緵 HTTP 鎺ュ彛绠＄悊 run_id 閰嶇疆銆?
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from ..run_id_manager import run_id_manager
from app.service.auth.core.dependencies import get_current_admin_user

# 瀵煎叆韬唤楠岃瘉渚濊禆


router = APIRouter()


class SetActiveRunIDRequest(BaseModel):
    """璁剧疆娲昏穬 run_id 鐨勮姹備綋"""
    run_id: str
    updated_by: Optional[str] = None
    notes: Optional[str] = None


@router.get("/run-ids/active")
def get_all_active_run_ids():
    """
    鑾峰彇鎵€鏈夊垎鏋愮被鍨嬬殑娲昏穬 run_id锛堝叕寮€绔偣锛?

    Returns:
        鎵€鏈夊垎鏋愮被鍨嬬殑娲昏穬 run_id 閰嶇疆
    """
    try:
        result = run_id_manager.get_all_active_run_ids()
        return {
            "success": True,
            "data": result,
            "count": len(result)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/run-ids/active/{analysis_type}")
def get_active_run_id(
    analysis_type: str  # 娣诲姞閫熺巼闄愬埗锛屼絾鍏佽鍖垮悕璁块棶
):
    """
    鑾峰彇鎸囧畾鍒嗘瀽绫诲瀷鐨勬椿璺?run_id锛堝叕寮€绔偣锛?

    Args:
        analysis_type: 鍒嗘瀽绫诲瀷鏍囪瘑

    Returns:
        娲昏穬鐨?run_id 閰嶇疆
    """
    try:
        run_id = run_id_manager.get_active_run_id(analysis_type)
        return {
            "success": True,
            "analysis_type": analysis_type,
            "run_id": run_id
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
    鍒楀嚭鎸囧畾鍒嗘瀽绫诲瀷鐨勬墍鏈夊彲鐢?run_id

    Args:
        analysis_type: 鍒嗘瀽绫诲瀷鏍囪瘑

    Returns:
        鍙敤 run_id 鍒楄〃
    """
    try:
        run_ids = run_id_manager.list_available_run_ids(analysis_type)
        return {
            "success": True,
            "analysis_type": analysis_type,
            "available_run_ids": run_ids,
            "count": len(run_ids)
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
    璁剧疆娲昏穬 run_id锛堥渶瑕佺鐞嗗憳鏉冮檺锛?

    Args:
        analysis_type: 鍒嗘瀽绫诲瀷鏍囪瘑
        request: 鍖呭惈 run_id銆乽pdated_by銆乶otes 鐨勮姹備綋
        admin: 褰撳墠绠＄悊鍛樼敤鎴?

    Returns:
        鏇存柊缁撴灉
    """
    try:
        run_id_manager.set_active_run_id(
            analysis_type=analysis_type,
            run_id=request.run_id,
            updated_by=request.updated_by,
            notes=request.notes
        )

        return {
            "success": True,
            "message": f"宸插皢 {analysis_type} 鐨勬椿璺?run_id 鏇存柊涓?{request.run_id}",
            "analysis_type": analysis_type,
            "run_id": request.run_id
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
    鑾峰彇 run_id 鐨勮缁嗗厓鏁版嵁

    Args:
        run_id: run_id 鏍囪瘑

    Returns:
        run_id 鐨勫厓鏁版嵁
    """
    try:
        metadata = run_id_manager.get_run_id_metadata(run_id)
        return {
            "success": True,
            "data": metadata
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
    鍒锋柊 run_id 缂撳瓨

    Returns:
        鍒锋柊缁撴灉
    """
    try:
        run_id_manager.refresh_cache()
        return {
            "success": True,
            "message": "缓存刷新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


