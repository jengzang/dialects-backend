"""
Custom Regions编辑API端点（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.custom.region_service 中实现（已包含管理员功能）
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.service.user.submission.database import get_db
from app.service.user.submission import region_service
from app.schemas.admin import AdminRegionCreate, AdminRegionUpdate, AdminRegionDelete
import json

router = APIRouter()


@router.post("/create")
async def create_region(
    data: AdminRegionCreate,
    db: Session = Depends(get_db)
):
    """管理员为任意用户创建区域"""
    try:
        region = region_service.create_region_admin(
            db, data.username, data.region_name, data.locations, data.description
        )
        locations = json.loads(region.locations)
        return {
            "success": True,
            "region": {
                "id": region.id,
                "user_id": region.user_id,
                "username": region.username,
                "region_name": region.region_name,
                "locations": locations,
                "location_count": len(locations),
                "description": region.description,
                "created_at": region.created_at.isoformat(),
                "updated_at": region.updated_at.isoformat()
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
        region = region_service.update_region_admin(
            db, data.username, data.region_name,
            data.new_region_name, data.locations, data.description
        )
        locations = json.loads(region.locations)
        return {
            "success": True,
            "region": {
                "id": region.id,
                "user_id": region.user_id,
                "username": region.username,
                "region_name": region.region_name,
                "locations": locations,
                "location_count": len(locations),
                "description": region.description,
                "created_at": region.created_at.isoformat(),
                "updated_at": region.updated_at.isoformat()
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
        success = region_service.delete_region_admin(db, data.username, data.created_at)
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
        deleted_count, failed = region_service.batch_delete_regions_admin(db, regions_data)
        return {
            "success": True,
            "deleted_count": deleted_count,
            "failed": failed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")
