import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional

import redis
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.auth import models
from app.auth.database import get_db
from app.auth.models import User, ApiUsageLog
from common.config import SECRET_KEY, ALGORITHM, MAX_USER_USAGE_PER_HOUR, \
    MAX_IP_USAGE_PER_HOUR, MAX_LOGIN_PER_MINUTE, CACHE_EXPIRATION_TIME  # 根據你的設定實際調整

# 配置 Redis 连接
redis_client = redis.StrictRedis(host='172.28.199.1', port=6379, db=0, decode_responses=True)


def user_to_dict(user: models.User) -> dict:
    user_dict = {column.name: getattr(user, column.name) for column in user.__table__.columns}

    # 将 datetime 类型字段转换为字符串
    for key, value in user_dict.items():
        if isinstance(value, datetime):
            user_dict[key] = value.isoformat()  # 转换为 ISO 8601 字符串格式
    return user_dict
async def get_current_user(
        request: Request,
        db: Session = Depends(get_db),
        require_admin: bool = False  # ✅ 預設不要求管理員
) -> models.User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        if not require_admin:
            return None  # 匿名用户
        else:
            raise HTTPException(status_code=401, detail="未登錄用戶沒有訪問此資源的權限")
    else:
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            # username = payload.get("sub")
            username = payload.get("sub")  # 从 JWT 中提取邮箱作为唯一标识
            if not username:
                return None  # Token 無效
        except JWTError:
            return None  # Token 解碼失敗

    # 1. 首先检查缓存中是否存在该用户
    cached_user = redis_client.get(f"user:{username}")
    if cached_user:
        # 如果缓存中有数据，反序列化为 User 对象
        cached_data = json.loads(cached_user)  # 获取缓存的 JSON 字符串
        user = models.User(**cached_data)  # 使用 User 的字段初始化 User 对象
        print(f"使用缓存:{username}")
        return user

    # 2. 如果缓存中没有，查询数据库
    # print("啥都没存,我还是查库")
    user = db.query(models.User).filter(models.User.username == username).first()
    # print(user)
    if not user:
        return None  # 用户不存在

        # 将用户信息存入缓存，并设置过期时间
    try:
        cache_result =  redis_client.setex(f"user:{username}", CACHE_EXPIRATION_TIME, json.dumps(user_to_dict(user)))
        if cache_result:
            print(f"缓存写入成功: user:{username}")
        else:
            print(f"缓存写入失败: user:{username}")
    except Exception as e:
        print(f"写入缓存时发生错误: {e}")

    if require_admin and user.role != "admin":
        raise HTTPException(status_code=403, detail="你沒有訪問此資源的權限")

    return user


def get_current_user_sync(request: Request, db: Session) -> User:
    # 处理用户认证（例如从请求头获取 JWT token）
    auth_header = request.headers.get("Authorization")
    # 打印调试信息，查看 token
    # print(f"Authorization header: {auth_header}")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None  # 匿名用户，返回 None

    token = auth_header.split(" ")[1]
    try:
        # 解码 JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")  # 使用邮箱作为唯一标识
        if not username:
            return None  # Token 无效，返回 None
    except JWTError as e:
        print(f"JWT decode error: {e}")  # 打印错误信息，帮助调试
        return None  # 如果解码失败，返回 None

    # 1. 首先检查缓存中是否存在该用户
    cached_user = redis_client.get(f"user:{username}")
    if cached_user:
        # 如果缓存中有数据，反序列化为 User 对象
        cached_data = json.loads(cached_user)  # 获取缓存的 JSON 字符串
        user = models.User(**cached_data)  # 使用 User 的字段初始化 User 对象
        return user

    # 2. 如果缓存中没有，查询数据库
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return None  # 用户不存在，返回 None

    # 将用户信息存入缓存，并设置过期时间
    redis_client.setex(f"user:{username}", CACHE_EXPIRATION_TIME, json.dumps(user_to_dict(user)))

    return user

def get_current_admin_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user is None:
        raise HTTPException(status_code=401, detail="Token 无效或用户不存在")
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="你没有访问此资源的权限")
    return current_user


def check_api_usage_limit(
        db: Session,
        user: Optional[User],
        require_login: bool = False,  # 如果这个接口必须登录，设为 True
        ip_address: Optional[str] = None  # 添加 ip_address 参数来处理未登录用户
) -> None:
    """
    - 未登录: 默认放行（可选登录）；如需强制登录，传 require_login=True。
    - 管理员: 不限流。
    - 普通用户: 最近 1 小时内 duration 累积不得超过 MAX_(IP/USER)_USAGE_PER_HOUR 秒。
    - 未登录用户: 根据 IP 地址限制流量。
    """
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    print(user)
    # 1) 可选登录场景处理
    if user is None:
        if require_login:  # 匿名用户：无法按用户做配额，这里选择放行（如需限制可改为 raise 或基于 IP 做限流）
            # print("1111")
            raise HTTPException(status_code=401, detail="💡 請先登錄")
        # 未登录用户，按 IP 进行限制
        if ip_address is None:
            raise HTTPException(status_code=400, detail="🚫 IP 地址缺失")

        # 从数据库获取当前 IP 在过去一小时内的总使用时长
        total_duration = db.execute(
            select(func.coalesce(func.sum(ApiUsageLog.duration), 0))
            .where(ApiUsageLog.ip == ip_address)
            .where(ApiUsageLog.called_at >= one_hour_ago)
        ).scalar()

        if total_duration >= MAX_IP_USAGE_PER_HOUR:
            raise HTTPException(status_code=429,
                                detail="❌ API使用已達每小時上限，請稍後再試\n ✨ 小提醒：登入帳號可繼續查詢！🚀")

        return
    # 2)管理員不受限制
    if user.role == "admin":
        return
    # 3)已登錄用戶根據用戶名
    total_duration = db.execute(
        select(func.coalesce(func.sum(ApiUsageLog.duration), 0))
        .where(ApiUsageLog.user_id == user.id)
        .where(ApiUsageLog.called_at >= one_hour_ago)
    ).scalar()

    if total_duration >= MAX_USER_USAGE_PER_HOUR:
        # 取出所有紀錄，按時間排序
        logs = db.execute(
            select(ApiUsageLog.called_at, ApiUsageLog.duration)
            .where(ApiUsageLog.user_id == user.id)
            .where(ApiUsageLog.called_at >= one_hour_ago)
            .order_by(ApiUsageLog.called_at.asc())
        ).all()

        remaining = total_duration - MAX_USER_USAGE_PER_HOUR

        released_time = None
        accumulated = 0.0

        for log_time, duration in logs:
            accumulated += duration
            if accumulated >= remaining:
                # 當這筆記錄過期後，限額才會釋放
                released_time = log_time + timedelta(hours=1)
                break

        if released_time:
            now = datetime.utcnow()
            wait_seconds = int((released_time - now).total_seconds())
            if wait_seconds > 0:
                wait_time_str = str(timedelta(seconds=wait_seconds))  # hh:mm:ss
                # ✅ 直接加 8 小時作為北京時間
                released_time_bj = released_time + timedelta(hours=8)
                formatted_time_bj = released_time_bj.strftime("%Y-%m-%d %H:%M:%S 北京時間")

                raise HTTPException(
                    status_code=429,
                    detail=(
                        f" 尊敬的 👤{user.username} ，您的API 使用配額已達本小時上限！⏳\n"
                        f" 請等待 ⏱️ {wait_time_str} 後再試。\n"
                        f"📅 可再次使用時間：{formatted_time_bj}\n"
                    )
                )


def check_login_rate_limit(db: Session, ip: str):
    one_minute_ago = datetime.utcnow() - timedelta(minutes=1)

    login_attempts = db.query(ApiUsageLog).filter(
        ApiUsageLog.ip == ip,
        ApiUsageLog.path == "/login",  # 僅計算登入路徑
        ApiUsageLog.called_at >= one_minute_ago
    ).count()

    if login_attempts >= MAX_LOGIN_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="🚫 登入過於頻繁，請稍候再試"
        )
