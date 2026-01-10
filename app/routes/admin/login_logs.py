from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import models
from app.auth.database import get_db

router = APIRouter()

# 获取成功登录日志，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.get("/success-login-logs")
def get_login_logs(query: str, db: Session = Depends(get_db)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 返回该用户的成功登录日志
    return db.query(models.ApiUsageLog).filter(
        models.ApiUsageLog.path == '/login',
        models.ApiUsageLog.user_id == user.id
    ).all()


# 获取登录失败记录，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.get("/failed-login-logs")
def get_failed_login_logs(query: str, db: Session = Depends(get_db)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 返回该用户的失败登录日志
    return db.query(models.ApiUsageLog).filter(
        models.ApiUsageLog.status_code != 200,
        models.ApiUsageLog.user_id == user.id
    ).all()
