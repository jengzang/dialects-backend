from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import models
from app.auth.database import get_db

router = APIRouter()

# 获取用户登录历史，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.get("/login-history")
def get_user_login_history(query: str, db: Session = Depends(get_db)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 返回该用户的登录历史
    return db.query(models.ApiUsageLog).filter(models.ApiUsageLog.user_id == user.id).all()


# 获取用户在线时长等统计信息，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.get("/stats")
def get_user_stats(query: str, db: Session = Depends(get_db)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()
    # print(db.query(models.User).filter(
    #     (models.User.username == query) | (models.User.email == query)
    # ).all())  # 這樣可以看到所有匹配的結果

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 返回该用户的统计信息
    return {
        "login_count": user.login_count,
        "failed_attempts": user.failed_attempts,
        "total_online_seconds": user.total_online_seconds,
        "last_login": user.last_login,
        "register_ip":user.register_ip,
    }
