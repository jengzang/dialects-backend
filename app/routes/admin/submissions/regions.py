"""
用户自定义区域管理API端点（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.service.user.submission.region_service 中实现

合并自：custom_regions.py + custom_regions_edit.py
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
import json

from app.service.user.core.database import get_db
from app.service.user.submission import region
from app.common.time_utils import to_shanghai_iso
from app.schemas.admin.submissions import (
    AdminRegionListResponse,
    AdminRegionCreate,
    AdminRegionUpdate,
    AdminRegionDelete
)

router = APIRouter()


# ========== 查询相关 ==========

@router.get("/all")
async def get_all_regions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取所有用户的自定义区域（分页）"""
    try:
        data, total = region.get_all_regions_admin(db, skip, limit, search)
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
        regions = region.get_regions_by_username_admin(db, username)
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
        counts = region.get_user_region_counts(db)
        return counts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/stats")
async def get_statistics(db: Session = Depends(get_db)):
    """获取区域统计信息"""
    try:
        stats = region.get_region_statistics(db)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


# ========== 编辑相关 ==========

@router.post("/create")
async def create_region(
    data: AdminRegionCreate,
    db: Session = Depends(get_db)
):
    """管理员为任意用户创建区域"""
    try:
        region_record = region.create_region_admin(
            db, data.username, data.region_name, data.locations, data.description
        )
        locations = json.loads(region_record.locations)
        return {
            "success": True,
            "region": {
                "id": region_record.id,
                "user_id": region_record.user_id,
                "username": region_record.username,
                "region_name": region_record.region_name,
                "locations": locations,
                "location_count": len(locations),
                "description": region_record.description,
                "created_at": to_shanghai_iso(region_record.created_at),
                "updated_at": to_shanghai_iso(region_record.updated_at)
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.put("/update")
async def update_region(
    data: AdminRegionUpdate,
    db: Session = Depends(get_db)
):
    """管理员更新任意用户的区域"""
    try:
        region_record = region.update_region_admin(
            db, data.username, data.region_name,
            data.new_region_name, data.locations, data.description
        )
        locations = json.loads(region_record.locations)
        return {
            "success": True,
            "region": {
                "id": region_record.id,
                "user_id": region_record.user_id,
                "username": region_record.username,
                "region_name": region_record.region_name,
                "locations": locations,
                "location_count": len(locations),
                "description": region_record.description,
                "created_at": to_shanghai_iso(region_record.created_at),
                "updated_at": to_shanghai_iso(region_record.updated_at)
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/delete")
async def delete_region(
    data: AdminRegionDelete,
    db: Session = Depends(get_db)
):
    """管理员删除任意用户的区域"""
    try:
        success = region.delete_region_admin(db, data.username, data.created_at)
        if success:
            return {
                "success": True,
                "deleted": True,
                "username": data.username,
                "created_at": data.created_at
            }
        else:
            raise HTTPException(status_code=404, detail="区域不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.post("/batch-delete")
async def batch_delete_regions(
    regions: List[AdminRegionDelete],
    db: Session = Depends(get_db)
):
    """批量删除区域"""
    try:
        regions_data = [{"username": r.username, "created_at": r.created_at} for r in regions]
        deleted_count, failed = region.batch_delete_regions_admin(db, regions_data)
        return {
            "success": True,
            "deleted_count": deleted_count,
            "failed": failed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")

