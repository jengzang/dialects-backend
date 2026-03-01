from fastapi import APIRouter, Depends, HTTPException, Query
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
def get_all_api_usage(
    skip: int = Query(None, ge=0, description="分页偏移（可选）"),
    limit: int = Query(None, ge=1, le=500, description="分页限制（可选）"),
    db: Session = Depends(get_db)
):
    # 使用 JOIN 查询避免 N+1 问题
    query = db.query(
        models.ApiUsageLog,
        models.User.username
    ).outerjoin(
        models.User,
        models.ApiUsageLog.user_id == models.User.id
    ).filter(
        models.ApiUsageLog.path != '/login'
    ).order_by(models.ApiUsageLog.called_at.desc())

    # 如果提供了分页参数，返回分页格式
    if skip is not None or limit is not None:
        # 获取总数
        total = query.count()

        # 应用分页
        skip = skip or 0
        limit = limit or 100
        logs = query.offset(skip).limit(limit).all()

        # 构建结果
        result = []
        for log, username in logs:
            os, browser = extract_device_info(log.user_agent)
            result.append({
                "user": username or '',
                "ip": log.ip,
                "path": log.path,
                "duration": log.duration,
                "os": os,
                "browser": browser,
                "called_at": log.called_at.strftime("%Y-%m-%d %H:%M:%S"),
                "request_size": log.request_size,
                "response_size": log.response_size,
            })

        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "data": result
        }

    # 如果没有分页参数，返回所有数据（向后兼容）
    else:
        logs = query.all()

        result = []
        for log, username in logs:
            os, browser = extract_device_info(log.user_agent)
            result.append({
                "user": username or '',
                "ip": log.ip,
                "path": log.path,
                "duration": log.duration,
                "os": os,
                "browser": browser,
                "called_at": log.called_at.strftime("%Y-%m-%d %H:%M:%S"),
                "request_size": log.request_size,
                "response_size": log.response_size,
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