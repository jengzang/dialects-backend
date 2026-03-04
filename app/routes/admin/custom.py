"""
Custom数据管理API端点（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.custom.admin.custom_service 中实现
"""
from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.custom.database import SessionLocal as SessionLocal_info
from app.auth.database import SessionLocal as SessionLocal_user
from app.schemas.admin import InformationBase
from app.custom.admin import custom_service

router = APIRouter()


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