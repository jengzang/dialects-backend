# app/routes/user/custom_regions.py
"""
用户自定义区域 API 端点
允许用户创建、更新、删除和查询自己的地点分组
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.service.user.core.database import get_db
from app.service.user.submission import region as region_service
from app.schemas.user.submissions import (
    CustomRegionCreate,
    CustomRegionList
)
from app.service.auth.core.dependencies import get_current_user
from app.common.time_utils import to_shanghai_iso
# from app.logging.dependencies.limiter import ApiLimiter
from app.service.auth.database.models import User

router = APIRouter()


@router.post("/api/custom_regions", response_model=dict)
async def create_or_update_custom_region(
    data: CustomRegionCreate,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    """
    创建或更新自定义区域

    - 如果区域名称已存在，则更新（覆盖）
    - 如果区域名称不存在，则创建新区域
    - 需要登录认证
    """
    # 检查用户是否登录
    if not user:
        raise HTTPException(status_code=401, detail="需要登录才能创建自定义区域")

    try:
        # 创建或更新区域
        region_record, action = region_service.create_or_update_region(
            db=db,
            user_id=user.id,
            username=user.username,
            region_name=data.region_name,
            locations=data.locations,
            description=data.description
        )

        # 构造响应
        import json
        return {
            "success": True,
            "action": action,
            "region": {
                "id": region_record.id,
                "region_name": region_record.region_name,
                "locations": json.loads(region_record.locations),
                "description": region_record.description,
                "created_at": to_shanghai_iso(region_record.created_at),
                "updated_at": to_shanghai_iso(region_record.updated_at)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建/更新区域失败: {str(e)}")


@router.delete("/api/custom_regions", response_model=dict)
async def delete_custom_region(
    region_name: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    """
    删除自定义区域

    - 需要登录认证
    - 只能删除自己的区域
    """
    # 检查用户是否登录
    if not user:
        raise HTTPException(status_code=401, detail="需要登录才能删除自定义区域")

    try:
        # 删除区域
        deleted = region_service.delete_region(
            db=db,
            user_id=user.id,
            region_name=region_name
        )

        if deleted:
            return {
                "success": True,
                "deleted": True,
                "region_name": region_name
            }
        else:
            raise HTTPException(status_code=404, detail="区域不存在或无权删除")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除区域失败: {str(e)}")


@router.get("/api/custom_regions", response_model=CustomRegionList)
async def get_custom_regions(
    region_name: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    """
    获取用户的自定义区域列表

    - 需要登录认证
    - 可选：通过 region_name 参数筛选特定区域
    - 未登录用户返回空列表
    """
    # 未登录用户返回空列表
    if not user:
        return CustomRegionList(success=True, regions=[], total=0)

    try:
        # 获取区域列表
        regions = region_service.get_user_regions(
            db=db,
            user_id=user.id,
            region_name=region_name
        )

        return CustomRegionList(
            success=True,
            regions=regions,
            total=len(regions)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取区域列表失败: {str(e)}")
