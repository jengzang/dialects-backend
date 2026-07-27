"""
登录日志业务逻辑层

职责：
- 查询成功登录日志（基于 sessions 表）
- 查询失败登录日志（基于 api_usage_logs 表，按 IP 关联）
- 登录统计

注意：此模块不依赖FastAPI，可在任何地方调用
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.service.auth.database import models
from app.service.admin.analytics.geo import lookup_ip_location


LOGIN_PATHS = ('/login', '/auth/login', '/api/auth/login')


def get_success_login_logs(db: Session, query: str) -> Optional[List[Dict[str, Any]]]:
    """
    获取成功登录日志（基于 sessions 表）

    每次登录成功都会创建一条 session 记录，有完整的 user_id、IP、设备信息。
    不再依赖 api_usage_logs 表，因为登录请求没有 auth header，
    中间件无法解析 user_id，导致 api_usage_logs 中 user_id 为 NULL。

    Args:
        db: 数据库会话
        query: 用户名或邮箱

    Returns:
        登录日志列表，如果用户不存在则返回None
    """
    if not query:
        return None

    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        return None

    sessions = db.query(models.Session).filter(
        models.Session.user_id == user.id
    ).order_by(models.Session.created_at.desc()).all()

    result = []
    for s in sessions:
        result.append({
            "id": s.id,
            "user_id": s.user_id,
            # 登录时
            "login_at": s.created_at,
            "login_ip": s.first_ip,
            "login_ip_location": lookup_ip_location(s.first_ip) if s.first_ip else None,
            "login_device": s.first_device_info,
            # 当前
            "current_ip": s.current_ip,
            "current_ip_location": lookup_ip_location(s.current_ip) if s.current_ip else None,
            "current_device": s.device_info,
            # 会话状态
            "revoked": s.revoked,
            "revoked_reason": s.revoked_reason,
            "revoked_at": s.revoked_at,
            "expires_at": s.expires_at,
            "last_activity_at": s.last_activity_at,
            # 统计
            "total_online_seconds": s.total_online_seconds,
            "ip_change_count": s.ip_change_count,
            "refresh_count": s.refresh_count,
        })

    return result


def get_failed_login_logs(db: Session, query: str) -> Optional[List[Dict[str, Any]]]:
    """
    获取失败登录日志（基于 api_usage_logs 表，按已知 IP 关联）

    失败登录不创建 session，所以仍需查 api_usage_logs。
    由于登录请求的 user_id 为 NULL，改为通过该用户历史 session 中出现过的 IP
    来匹配失败登录记录。

    Args:
        db: 数据库会话
        query: 用户名或邮箱

    Returns:
        登录日志列表，如果用户不存在则返回None
    """
    if not query:
        return None

    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        return None

    # 收集该用户历史上用过的所有 IP
    user_ips = set()
    user_sessions = db.query(models.Session).filter(
        models.Session.user_id == user.id
    ).all()
    for s in user_sessions:
        if s.first_ip:
            user_ips.add(s.first_ip)
        if s.current_ip:
            user_ips.add(s.current_ip)

    if not user_ips:
        return []

    logs = db.query(models.ApiUsageLog).filter(
        models.ApiUsageLog.path.in_(LOGIN_PATHS),
        models.ApiUsageLog.status_code != 200,
        models.ApiUsageLog.ip.in_(user_ips),
    ).order_by(models.ApiUsageLog.called_at.desc()).all()

    result = []
    for log in logs:
        result.append({
            "id": log.id,
            "user_id": user.id,
            "path": log.path,
            "duration": log.duration,
            "status_code": log.status_code,
            "ip": log.ip,
            "ip_location": lookup_ip_location(log.ip) if log.ip else None,
            "user_agent": log.user_agent,
            "referer": log.referer,
            "called_at": log.called_at,
        })

    return result
