"""
用户提交数据管理API端点（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.service.admin.submissions.management 中实现

合并自：custom.py + custom_edit.py
"""
from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.service.user.core.database import SessionLocal as SessionLocal_info
from app.service.auth.database.connection import SessionLocal as SessionLocal_user
from app.schemas.admin import InformationBase, EditRequest
from app.service.admin.submissions import management as custom_service

router = APIRouter()


# ========== 查询相关 ==========

@router.get("/all", response_model=List[InformationBase])
async def get_informations():
    """获取所有用户的custom数据"""
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        result = custom_service.get_all_custom_data(session_info, session_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()
        session_user.close()


@router.get("/num")
async def get_user_data_count():
    """获取每个用户的数据数量"""
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        result = custom_service.get_user_data_count(session_info, session_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()
        session_user.close()


@router.get("/user", response_model=List[InformationBase])
async def get_custom_peruser(query: str = Query(..., description="用戶名")):
    """根据用户名查询用户数据"""
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        user_data = custom_service.get_custom_by_username(session_info, session_user, query)

        if user_data is None:
            raise HTTPException(status_code=404, detail="用戶未找到")

        if not user_data:
            return []

        return user_data
    except HTTPException:
        raise
    except Exception as e:
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


# ========== 编辑相关 ==========

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
            requests_dict
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
