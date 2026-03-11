"""
登录日志业务逻辑层

职责：
- 查询成功登录日志
- 查询失败登录日志
- 登录统计

注意：此模块不依赖FastAPI，可在任何地方调用
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.service.auth import models
from app.service.admin.analytics.geo import lookup_ip_location


def get_success_login_logs(db: Session, query: str) -> Optional[List[Dict[str, Any]]]:
    """
    获取成功登录日志

    Args:
        db: 数据库会话
        query: 用户名或邮箱

    Returns:
        登录日志列表，如果用户不存在则返回None
    """
    if not query:
        return None

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        return None

    # 查询该用户的成功登录日志
    logs = db.query(models.ApiUsageLog).filter(
        models.ApiUsageLog.path == '/login',
        models.ApiUsageLog.user_id == user.id
    ).all()

    # 添加地理位置信息
    result = []
    for log in logs:
        log_dict = {
            "id": log.id,
            "user_id": log.user_id,
            "path": log.path,
            "duration": log.duration,
            "status_code": log.status_code,
            "ip": log.ip,
            "ip_location": lookup_ip_location(log.ip) if log.ip else None,
            "user_agent": log.user_agent,
            "referer": log.referer,
            "called_at": log.called_at
        }
        result.append(log_dict)

    return result


def get_failed_login_logs(db: Session, query: str) -> Optional[List[Dict[str, Any]]]:
    """
    获取失败登录日志

    Args:
        db: 数据库会话
        query: 用户名或邮箱

    Returns:
        登录日志列表，如果用户不存在则返回None
    """
    if not query:
        return None

    # 查找用户，支持通过 username 或 email 查找
    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        return None

    # 查询该用户的失败登录日志
    logs = db.query(models.ApiUsageLog).filter(
        models.ApiUsageLog.status_code != 200,
        models.ApiUsageLog.user_id == user.id
    ).all()

    # 添加地理位置信息
    result = []
    for log in logs:
        log_dict = {
            "id": log.id,
            "user_id": log.user_id,
            "path": log.path,
            "duration": log.duration,
            "status_code": log.status_code,
            "ip": log.ip,
            "ip_location": lookup_ip_location(log.ip) if log.ip else None,
            "user_agent": log.user_agent,
            "referer": log.referer,
            "called_at": log.called_at
        }
        result.append(log_dict)

    return result
