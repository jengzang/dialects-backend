"""
API使用统计API端点（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.admin.api_usage_service 中实现
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.auth.database import get_db
from app.admin import api_usage_service
from typing import Optional, Literal

router = APIRouter()


# 获取用户的 API 使用统计，通过 username 或 email 查找
@router.get("/api-summary")
def get_api_usage_summary(query: str, db: Session = Depends(get_db)):
    """获取用户的API使用摘要"""
    result = api_usage_service.get_api_usage_summary(db, query)

    if result is None:
        raise HTTPException(status_code=400, detail="Query parameter is required or user not found")

    return result


@router.get("/api-detail")
def get_user_api_usage(query: str, db: Session = Depends(get_db)):
    """获取用户的API使用详情"""
    result = api_usage_service.get_user_api_detail(db, query)

    if result is None:
        raise HTTPException(status_code=400, detail="Query parameter is required or user not found")

    return result


# 通过查询日志数据获取指定字段（增强版：支持搜索、排序、统计）
@router.get("/api-usage")
def get_all_api_usage(
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(50, ge=1, le=500, description="分页限制"),
    search: Optional[str] = Query(None, description="搜索关键词（匹配 user/ip/path/os/browser）"),
    sort_by: Optional[Literal["user", "ip", "path", "duration", "os", "browser", "called_at", "request_size", "response_size"]] = Query(None, description="排序字段"),
    sort_order: Optional[Literal["asc", "desc"]] = Query("desc", description="排序方向"),
    include_stats: bool = Query(False, description="是否返回全局统计信息"),
    db: Session = Depends(get_db)
):
    """
    获取 API 使用日志（增强版）

    支持功能：
    - 分页：skip, limit
    - 搜索：search（匹配 user/ip/path/os/browser）
    - 排序：sort_by, sort_order
    - 统计：include_stats（返回全局统计信息）
    """
    return api_usage_service.get_all_api_usage(
        db=db,
        skip=skip,
        limit=limit,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        include_stats=include_stats
    )