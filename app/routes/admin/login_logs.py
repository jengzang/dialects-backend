"""
登录日志API端点（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.admin.login_log_service 中实现
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import models
from app.auth.database import get_db
from app.admin import login_log_service

router = APIRouter()


# 获取成功登录日志，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.get("/success-login-logs")
def get_login_logs(query: str, db: Session = Depends(get_db)):
    """获取成功登录日志"""
    result = login_log_service.get_success_login_logs(db, query)

    if result is None:
        raise HTTPException(status_code=400, detail="Query parameter is required or user not found")

    return result


# 获取登录失败记录，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.get("/failed-login-logs")
def get_failed_login_logs(query: str, db: Session = Depends(get_db)):
    """获取失败登录日志"""
    result = login_log_service.get_failed_login_logs(db, query)

    if result is None:
        raise HTTPException(status_code=400, detail="Query parameter is required or user not found")

    return result
