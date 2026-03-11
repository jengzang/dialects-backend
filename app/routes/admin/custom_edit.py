"""
Custom数据编辑API端点（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.custom.admin.custom_service 中实现
"""
from typing import List

from fastapi import HTTPException, APIRouter

from app.service.user.submission.database import SessionLocal as SessionLocal_info
from app.service.auth.database import SessionLocal as SessionLocal_user
from app.schemas.admin import EditRequest, InformationBase
from app.service.admin import custom_service

router = APIRouter()


@router.delete("/delete", response_model=List[InformationBase])
async def delete_custom_by_admin(
    requests: List[EditRequest]
):
    """管理员删除custom数据"""
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        # 转换为字典列表
        requests_dict = [{"username": r.username, "created_at": r.created_at} for r in requests]

        result = custom_service.delete_custom_by_admin(
            session_info,
            session_user,
            requests_dict,
            current_user
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result["deleted_records"]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session_info.close()
        session_user.close()


@router.post("/create", response_model=List[InformationBase])
async def create_custom_by_admin(infos: List[InformationBase]):
    """管理员创建custom数据"""
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        # 转换为字典列表
        infos_dict = [info.dict() for info in infos]

        result = custom_service.create_custom_by_admin(
            session_info,
            session_user,
            infos_dict
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        # 转换为 Pydantic 模型返回
        return [InformationBase.from_orm(record) for record in result["created_records"]]

    except HTTPException:
        raise
    except Exception as e:
        session_info.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()
        session_user.close()


@router.post("/selected", response_model=List[InformationBase])
async def selected_custom(requests: List[EditRequest]):
    """根据条件查询custom数据"""
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        # 转换为字典列表
        requests_dict = [{"username": r.username, "created_at": r.created_at} for r in requests]

        result = custom_service.get_selected_custom(
            session_info,
            session_user,
            requests_dict
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result["data"]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()
        session_user.close()