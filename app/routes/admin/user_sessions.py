"""
基于 Session 模型的会话管理 API（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.admin.sessions 中实现

推荐使用此 API 替代 /admin/sessions/* (基于 RefreshToken)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from typing import Optional
from datetime import datetime

from app.auth.dependencies import get_current_admin_user
from app.auth.models import User
from app.auth.database import get_db
from app.admin.sessions import core, stats, activity
from app.schemas.session import (
    SessionDetailResponse,
    SessionListResponse,
    SessionStatsResponse,
    SessionActivityResponse,
    RevokeSessionResponse,
    RevokeBulkResponse,
    FlagSessionRequest,
    AnalyticsResponse,
    OnlineUsersResponse
)

router = APIRouter()


@router.get("/list", response_model=SessionListResponse)
def list_sessions(
    user_id: Optional[int] = Query(None, description="按用户 ID 筛选"),
    username: Optional[str] = Query(None, description="按用户名筛选"),
    is_suspicious: Optional[bool] = Query(None, description="筛选可疑会话"),
    revoked: Optional[bool] = Query(None, description="筛选撤销状态"),
    ip_address: Optional[str] = Query(None, description="按当前 IP 筛选"),
    created_after: Optional[datetime] = Query(None, description="创建时间范围（起）"),
    created_before: Optional[datetime] = Query(None, description="创建时间范围（止）"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 (asc/desc)"),
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=500, description="分页限制"),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """列出会话（高级过滤）"""
    result = core.list_sessions(
        db=db,
        user_id=user_id,
        username=username,
        is_suspicious=is_suspicious,
        revoked=revoked,
        ip_address=ip_address,
        created_after=created_after,
        created_before=created_before,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit
    )
    return SessionListResponse(**result)


@router.get("/stats", response_model=SessionStatsResponse)
def get_session_stats(
    start_date: Optional[datetime] = Query(None, description="统计开始时间"),
    end_date: Optional[datetime] = Query(None, description="统计结束时间"),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """会话统计仪表板"""
    result = stats.get_session_stats(db, start_date, end_date)
    return SessionStatsResponse(**result)


@router.post("/revoke-bulk", response_model=RevokeBulkResponse)
def revoke_sessions_bulk(
    session_ids: list[int],
    reason: Optional[str] = Query(None, max_length=200),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """批量撤销会话"""
    result = core.revoke_sessions_bulk(db, session_ids, reason)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return RevokeBulkResponse(**result)


@router.post("/revoke-user/{user_id}")
def revoke_user_sessions(
    user_id: int,
    reason: Optional[str] = Query(None, max_length=200),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """撤销用户的所有会话"""
    result = core.revoke_user_sessions(db, user_id, reason)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/user/{user_id}/history", response_model=SessionListResponse)
def get_user_session_history(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """获取用户的会话历史"""
    result = stats.get_user_session_history(db, user_id, skip, limit)

    if result is None:
        raise HTTPException(status_code=404, detail="User not found")

    return SessionListResponse(**result)


@router.get("/online-users", response_model=OnlineUsersResponse)
def get_online_users(
    threshold_minutes: int = Query(5, ge=1, le=120, description="在线判断阈值（分钟）"),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """获取实时在线用户列表"""
    result = stats.get_online_users(db, threshold_minutes)
    return OnlineUsersResponse(**result)


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(
    days: int = Query(30, ge=1, le=365, description="分析天数"),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """会话分析（时间序列、地理分布、设备分布）"""
    result = stats.get_analytics(db, days)
    return AnalyticsResponse(**result)


@router.get("/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(
    session_id: int,
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """获取会话详情"""
    result = core.get_session_detail(db, session_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return result


@router.get("/{session_id}/activity", response_model=SessionActivityResponse)
def get_session_activity(
    session_id: int,
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """获取会话活动时间线"""
    result = activity.get_session_activity(db, session_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionActivityResponse(**result)


@router.post("/{session_id}/revoke", response_model=RevokeSessionResponse)
def revoke_session(
    session_id: int,
    reason: str = Query("admin_action", max_length=100),
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """撤销单个会话"""
    result = core.revoke_session(db, session_id, reason)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return RevokeSessionResponse(
        message="Session revoked successfully",
        session=result["session"]
    )


@router.post("/{session_id}/flag", response_model=SessionDetailResponse)
def flag_session(
    session_id: int,
    request: FlagSessionRequest,
    db: DBSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    """标记会话为可疑/正常"""
    result = core.flag_session(
        db,
        session_id,
        request.is_suspicious,
        request.reason
    )

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return result["session"]
