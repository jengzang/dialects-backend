"""
Admin leaderboard routes for viewing global rankings.

Provides endpoints for:
- User global rankings (aggregated across all APIs)
- User rankings by specific API
- API endpoint rankings
- Online time rankings
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Literal, Optional
from app.service.auth.database.connection import get_db
from app.schemas.admin.analytics import (
    LeaderboardResponse,
    AvailableApisResponse
)
from app.service.admin.users import leaderboard as leaderboard_service

router = APIRouter()


@router.get("/rankings", response_model=LeaderboardResponse)
def get_rankings(
    ranking_type: Literal["user_global", "user_by_api", "api", "online_time"] = Query(...),
    metric: Optional[Literal["count", "duration", "upload", "download"]] = Query(None),
    api_path: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取排行榜数据

    - **ranking_type**: 排行类型
      - user_global: 用户全局排行（所有API汇总）
      - user_by_api: 单个API的用户排行
      - api: API端点排行
      - online_time: 在线时长排行
    - **metric**: 指标（online_time类型不需要）
      - count: 调用次数
      - duration: 使用时长
      - upload: 上行流量
      - download: 下行流量
    - **api_path**: API路径（仅user_by_api类型需要）
    - **page**: 页码
    - **page_size**: 每页数量
    """
    # 参数验证
    if ranking_type == "online_time":
        if metric is not None:
            raise HTTPException(400, "online_time类型不需要metric参数")
        rankings, total, total_value = leaderboard_service.get_online_time_ranking(db, page, page_size)
    elif ranking_type == "user_by_api":
        if not api_path:
            raise HTTPException(400, "user_by_api类型需要api_path参数")
        if not metric:
            raise HTTPException(400, "user_by_api类型需要metric参数")
        rankings, total, total_value = leaderboard_service.get_user_by_api_ranking(
            db, api_path, metric, page, page_size
        )
    elif ranking_type == "user_global":
        if not metric:
            raise HTTPException(400, "user_global类型需要metric参数")
        rankings, total, total_value = leaderboard_service.get_user_global_ranking(
            db, metric, page, page_size
        )
    elif ranking_type == "api":
        if not metric:
            raise HTTPException(400, "api类型需要metric参数")
        rankings, total, total_value = leaderboard_service.get_api_ranking(
            db, metric, page, page_size
        )
    else:
        raise HTTPException(400, f"不支持的排行类型: {ranking_type}")

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return LeaderboardResponse(
        ranking_type=ranking_type,
        metric=metric,
        api_path=api_path,
        total_count=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        rankings=rankings,
        total_value=total_value
    )


@router.get("/available-apis", response_model=AvailableApisResponse)
def get_available_apis(db: Session = Depends(get_db)):
    """
    获取所有可用的API路径列表

    返回系统中所有有使用记录的API路径，供前端构建下拉菜单使用。
    """
    apis = leaderboard_service.get_available_apis(db)
    return AvailableApisResponse(apis=apis)
