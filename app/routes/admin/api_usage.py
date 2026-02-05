from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import models
from app.auth.database import get_db

router = APIRouter()

# 获取用户的 API 使用统计，通过 username 或 email 查找
@router.get("/api-summary")
def get_api_usage_summary(query: str, db: Session = Depends(get_db)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 返回该用户的 API 使用统计
    return db.query(models.ApiUsageSummary).filter(models.ApiUsageSummary.user_id == user.id).all()


@router.get("/api-detail")
def get_user_api_usage(query: str, db: Session = Depends(get_db)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    api_logs = db.query(models.ApiUsageLog).filter(
        models.ApiUsageLog.user_id == user.id,
        models.ApiUsageLog.path != '/login'
    ).all()

    api_logs.sort(key=lambda log: log.called_at, reverse=True)

    # 返回 API 使用记录
    return {"user": user.username, "api_logs": api_logs}


# 通过查询日志数据获取指定字段
@router.get("/api-usage")
def get_all_api_usage(db: Session = Depends(get_db)):
    # 查询 api_usage_logs 表，排除 path='/login' 的记录
    logs = db.query(models.ApiUsageLog).filter(models.ApiUsageLog.path != '/login').all()

    # 将数据整理成需要的格式
    result = []
    for log in logs:
        # 提取操作系统和浏览器信息
        os, browser = extract_device_info(log.user_agent)
        # 查找用户名，如果没有找到则使用空字符串
        user = db.query(models.User).filter(models.User.id == log.user_id).first()
        username = user.username if user else ''  # 如果没有找到用户，用户名为空字符串

        # 构建返回数据
        result.append({
            "user": username,
            "ip": log.ip,
            "path": log.path,
            "duration": log.duration,
            "os": os,
            "browser": browser,
            "called_at": log.called_at.strftime("%Y-%m-%d %H:%M:%S"),
            "request_size":log.request_size,
            "response_size":log.response_size,
        })

    return result


# 提取设备信息（操作系统和浏览器）
def extract_device_info(user_agent: str):
    os = "Unknown OS"
    browser = "Unknown Browser"

    if "iPhone" in user_agent or "iPad" in user_agent:
        os = "iOS"
        browser = "Safari"
    elif "Android" in user_agent:
        os = "Android"
        browser = "Chrome"
    elif "Windows" in user_agent:
        os = "Windows"
        browser = "Chrome"
    elif "Macintosh" in user_agent:
        os = "Mac OS"
        browser = "Safari"
    elif "Linux" in user_agent:
        os = "Linux"
        browser = "Firefox"

    if "Chrome" in user_agent:
        browser = "Chrome"
    elif "Firefox" in user_agent:
        browser = "Firefox"
    elif "Safari" in user_agent:
        browser = "Safari"
    elif "Edge" in user_agent:
        browser = "Edge"

    return os, browser