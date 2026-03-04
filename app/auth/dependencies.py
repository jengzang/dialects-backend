import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.auth import models
from app.auth.database import get_db
from app.auth.models import User, ApiUsageLog
from app.auth.cache_security import sign_user_data, verify_user_data  # ✅ 导入签名函数
from app.redis_client import redis_client
from app.common.config import get_secret_key, ALGORITHM, MAX_LOGIN_PER_MINUTE, CACHE_EXPIRATION_TIME  # 根據你的設定實際調整
from app.common.api_config import MAX_USER_USAGE_PER_HOUR, MAX_IP_USAGE_PER_HOUR


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
        require_admin: bool = False  # [OK] 預設不要求管理員
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
            payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
            # username = payload.get("sub")
            username = payload.get("sub")  # 从 JWT 中提取邮箱作为唯一标识
            if not username:
                return None  # Token 無效
        except JWTError:
            return None  # Token 解碼失敗

    # 1. 首先检查缓存中是否存在该用户
    cached_user = await redis_client.get(f"user:{username}")
    if cached_user:
        # ✅ 验证签名
        user_dict = verify_user_data(cached_user)
        if user_dict:
            user = models.User(**user_dict)
            print(f"使用缓存:{username}")
            return user
        else:
            # 签名无效，删除缓存并重新查库
            print(f"[SECURITY] Invalid cache for {username}, re-fetching from DB")
            await redis_client.delete(f"user:{username}")

    # 2. 如果缓存中没有，查询数据库
    # print("啥都没存,我还是查库")
    user = db.query(models.User).filter(models.User.username == username).first()
    # print(user)
    if not user:
        return None  # 用户不存在

    # 将用户信息存入缓存，并设置过期时间
    try:
        # ✅ 签名数据后再存储
        signed_data = sign_user_data(user_to_dict(user))
        await redis_client.setex(
            f"user:{username}",
            CACHE_EXPIRATION_TIME,
            signed_data
        )
        print(f"[SAVE] 緩存寫入成功: user:{username}")
    except Exception as e:
        print(f"[X] 寫入緩存時發生錯誤: {e}")

    if require_admin and user.role != "admin":
        raise HTTPException(status_code=403, detail="你沒有訪問此資源的權限")

    return user


# [OK] 1. 改為 async def
async def get_current_user_for_middleware(request: Request, db: Session):
    # --- 前半部分邏輯不變 ---
    auth_header = request.headers.get("Authorization")
    # 打印调试信息，查看 token
    # print(f"Authorization header: {auth_header}")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None  # 匿名用户，返回 None

    token = auth_header.split(" ")[1]
    try:
        # 解码 JWT token
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
        username = payload.get("sub")  # 使用邮箱作为唯一标识
        if not username:
            return None  # Token 无效，返回 None
    except JWTError as e:
        print(f"JWT decode error: {e}")  # 打印错误信息，帮助调试
        return None  # 如果解码失败，返回 None

    # --- Redis 部分改為異步 ---
    try:
        # [OK] 2. 加上 await
        cached_user = await redis_client.get(f"user:{username}")
        if cached_user:
            # ✅ 验证签名
            user_dict = verify_user_data(cached_user)
            if user_dict:
                user = models.User(**user_dict)
                return user
            else:
                # 签名无效，删除缓存
                print(f"[SECURITY] Invalid cache for {username} in middleware")
                await redis_client.delete(f"user:{username}")
    except Exception as e:
        print(f"Redis error in middleware: {e}")
        # 如果 Redis 掛了，不要崩潰，繼續查數據庫

    # --- 數據庫部分 (保持同步阻塞) ---
    # [!] 注意：這裡 sql.query 是同步的，會稍微阻塞 Event Loop，但在中間件裡通常可以接受
    user = db.query(models.User).filter(models.User.username == username).first()

    if not user:
        return None

    # --- 寫回 Redis 改為異步 ---
    try:
        # ✅ 签名数据后再存储
        signed_data = sign_user_data(user_to_dict(user))
        await redis_client.setex(
            f"user:{username}",
            CACHE_EXPIRATION_TIME,
            signed_data
        )
    except Exception as e:
        print(f"Redis set error: {e}")

    return user

async def get_current_admin_user(
    request: Request,
    db: Session = Depends(get_db)
) -> models.User:
    """
    获取当前admin用户（必须从数据库验证）

    重要：不能只信任JWT中的role字段，必须从DB验证
    """
    import logging
    logger = logging.getLogger(__name__)

    # 解析JWT获取username和role
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登錄用戶沒有訪問此資源的權限")

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
        username = payload.get("sub")
        role_in_jwt = payload.get("role")  # JWT中的role（不能作为唯一依据）
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    # ✅ 从数据库验证role（最终权威）
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ⚠️ 安全检查：如果JWT的role和数据库不一致，记录安全事件
    if role_in_jwt and role_in_jwt != user.role:
        logger.warning(f"[SECURITY] Role mismatch for {username}: JWT={role_in_jwt}, DB={user.role}")
        # 可选：记录到安全日志表，或触发告警

    # ✅ 验证是否为admin（基于数据库中的role）
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return user


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
    # print(user)
    # 1) 可选登录场景处理
    if user is None:
        if require_login:  # 匿名用户：无法按用户做配额，这里选择放行（如需限制可改为 raise 或基于 IP 做限流）
            # print("1111")
            raise HTTPException(status_code=401, detail="[TIP] 請先登錄")
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
                                detail="[X] API使用已達每小時上限，請稍後再試\n [NEW] 小提醒：登入帳號可繼續查詢！[RUN]")

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
                # [OK] 直接加 8 小時作為北京時間
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
