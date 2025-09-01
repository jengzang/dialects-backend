from datetime import timedelta, datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.auth import utils, models
from app.schemas import auth as schemas
from common.config import REQUIRE_EMAIL_VERIFICATION, REGISTRATION_WINDOW_MINUTES, MAX_REGISTRATIONS_PER_IP


def register_user(db: Session, user: schemas.UserCreate, register_ip: str) -> models.User:
    # 限制：同 IP 10 分鐘最多註冊 3 次
    window_start = datetime.utcnow() - timedelta(minutes=REGISTRATION_WINDOW_MINUTES)

    recent_count = db.query(models.User).filter(
        models.User.register_ip == register_ip,
        models.User.created_at >= window_start
    ).count()

    if recent_count >= MAX_REGISTRATIONS_PER_IP:
        raise HTTPException(
            status_code=429,
            detail="🚫 該 IP 註冊過於頻繁，請稍後再試"
        )

    # 檢查帳號是否存在
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise ValueError("Username already exists")
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise ValueError("Email already exists")

    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=utils.get_password_hash(user.password),
        register_ip=register_ip,
        is_verified=not REQUIRE_EMAIL_VERIFICATION,
        login_count=0,
        failed_attempts=0,
        total_online_seconds=0,
        created_at=datetime.utcnow()  # ⬅️ 確保你有這個欄位！
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, username: str, password: str, login_ip: str) -> models.User:
    user = db.query(models.User).filter(
        or_(
            models.User.username == username,
            models.User.email == username
        )
    ).first()
    if not user:
        # 不暴露用户存在性
        raise ValueError("Invalid credentials")

    if not utils.verify_password(password, user.hashed_password):
        user.failed_attempts = (user.failed_attempts or 0) + 1
        user.last_failed_login = utils.now_utc_naive()
        db.commit()
        raise ValueError("Invalid credentials")

    # 未验证则阻断（注意：此时不应更新 last_login 等字段）
    if REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
        raise PermissionError("Email not verified")

    # 认证成功：更新登录信息 & 开启会话
    user.failed_attempts = 0
    user.last_login = utils.now_utc_naive()
    user.last_login_ip = login_ip
    user.login_count = (user.login_count or 0) + 1
    user.current_session_started_at = user.last_login
    user.last_seen = user.last_login
    db.commit()
    return user


# --- 登出：累加本次會話在線時長 ---
def logout_user(db: Session, user: models.User) -> int:
    """
    返回本次會話時長（秒）
    """
    now = utils.now_utc_naive()
    session_secs = 0
    if user.current_session_started_at:
        delta = now - user.current_session_started_at
        session_secs = int(delta.total_seconds())
        user.total_online_seconds = (user.total_online_seconds or 0) + session_secs
        user.current_session_started_at = None
    user.last_seen = now
    db.commit()
    return session_secs


# --- 心跳 / 訪問受保護接口時更新 last_seen（並分段累加在線時長）---
def touch_activity(db: Session, user: models.User) -> None:
    now = utils.now_utc_naive()

    # 若本次會話已開始，先把「上次觸達 → 本次觸達」這一段時間累加進總時長
    if user.current_session_started_at:
        delta = now - user.current_session_started_at
        seg_secs = int(delta.total_seconds())
        if seg_secs > 0:
            user.total_online_seconds = (user.total_online_seconds or 0) + seg_secs

    # 重置為新的分段起點，避免重複累加
    user.current_session_started_at = now

    # 更新最近活動時間
    user.last_seen = now
    db.commit()


# --- 簽發 token ---
def issue_token_for_user(user: models.User, minutes: int = utils.ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    return utils.create_access_token(subject=user.username, expires_minutes=minutes)


def update_user_profile(
        db: Session,
        email: str,  # 邮箱为必填项
        username: Optional[str] = None,  # 用户名可选
        password: Optional[str] = None,  # 当前密码可选
        new_password: Optional[str] = None,  # 新密码可选
) -> models.User:
    # 查询用户
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="用戶未找到")

    # 如果提供了当前密码（并且要修改密码），则验证当前密码
    if new_password and not password:
        raise HTTPException(status_code=400, detail="修改密碼時需要提供當前密碼")

    if password and not utils.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="當前密碼錯誤")

    # 如果提供了新的用户名，则修改用户名
    if username:
        # 验证用户名是否已存在
        existing_user = db.query(models.User).filter(models.User.username == username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="用戶名已存在")
        user.username = username  # 更新用户名

    # 如果提供了新密码，则修改密码
    if new_password:
        if len(new_password) < 6:
            raise HTTPException(status_code=400, detail="新密碼必須至少 6 個字符")
        user.hashed_password = utils.get_password_hash(new_password)  # 更新密码

    # 提交更改到数据库
    db.commit()
    db.refresh(user)

    return user

