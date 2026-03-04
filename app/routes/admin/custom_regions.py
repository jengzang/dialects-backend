"""
Custom Regions管理API端点（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.custom.region_service 中实现（已包含管理员功能）
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from app.custom.database import get_db
from app.custom import region_service
from app.schemas.admin import AdminRegionListResponse, UserRegionCount
from fastapi import Depends

router = APIRouter()


@router.get("/all")
async def get_all_regions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取所有用户的自定义区域（分页）"""
    try:
        data, total = region_service.get_all_regions_admin(db, skip, limit, search)
        return AdminRegionListResponse(total=total, skip=skip, limit=limit, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/user")
async def get_regions_by_user(
    username: str = Query(..., description="用户名"),
    db: Session = Depends(get_db)
):
    """按用户名查询区域"""
    try:
        regions = region_service.get_regions_by_username_admin(db, username)
        return {
            "username": username,
            "total": len(regions),
            "regions": regions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/count")
async def get_region_counts(db: Session = Depends(get_db)):
    """获取每个用户的区域数量"""
    try:
        counts = region_service.get_user_region_counts(db)
        return counts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/stats")
async def get_statistics(db: Session = Depends(get_db)):
    """获取区域统计信息"""
    try:
        stats = region_service.get_region_statistics(db)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
