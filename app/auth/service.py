from datetime import timedelta, datetime
from typing import Optional
import multiprocessing  # [FIX] 改用跨进程队列
import queue  # [FIX] 用于 queue.Empty 异常
import threading
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.auth import utils, models
from app.schemas import auth as schemas
from common.config import REQUIRE_EMAIL_VERIFICATION, REGISTRATION_WINDOW_MINUTES, MAX_REGISTRATIONS_PER_IP, \
    REFRESH_TOKEN_EXPIRE_DAYS, MAX_ACTIVE_REFRESH_TOKENS

# === 用户活动队列（跨进程） ===
# [FIX] 改用 multiprocessing.Queue 以支持主进程中的后台线程
user_activity_queue = multiprocessing.Queue()


# 用户活动更新数据结构
class UserActivityUpdate:
    def __init__(self, user_id: int, seconds_to_add: int = 0, update_last_seen: bool = True,
                 session_start_time: datetime = None):
        self.user_id = user_id
        self.seconds_to_add = seconds_to_add
        self.update_last_seen = update_last_seen
        self.session_start_time = session_start_time
        self.timestamp = datetime.utcnow()


# === 后台线程：批量处理用户活动更新 ===
def user_activity_writer():
    """后台线程：批量更新用户活动数据（动态策略）"""
    from app.auth.database import SessionLocal
    import time

    # 动态策略参数
    IMMEDIATE_THRESHOLD = 20      # 达到 50 条立即写入
    QUICK_THRESHOLD = 5          # 10 条且 1 分钟 → 写入
    QUICK_TIME = 30.0             # 1 分钟
    MAX_WAIT_TIME = 180         # 5 分钟必定写入

    batch = []
    last_write_time = time.time()

    while True:
        try:
            # 计算距离上次写入的时间
            time_elapsed = time.time() - last_write_time

            # 动态计算超时时间
            if len(batch) >= QUICK_THRESHOLD:
                # 已有 10 条，最多再等 1 分钟
                timeout = max(0.1, QUICK_TIME - time_elapsed)
            else:
                # 少于 10 条，最多等 5 分钟
                timeout = max(0.1, MAX_WAIT_TIME - time_elapsed)

            # 尝试获取新项
            try:
                item = user_activity_queue.get(timeout=timeout)
                if item is None:  # 停止信号
                    break
                batch.append(item)
            except queue.Empty:
                # 超时，检查是否需要写入
                pass

            # 动态决策：是否写入
            should_write = False
            reason = ""

            if len(batch) >= IMMEDIATE_THRESHOLD:
                # 策略1：达到 50 条立即写入
                should_write = True
                reason = f"达到 {IMMEDIATE_THRESHOLD} 条阈值"
            elif len(batch) >= QUICK_THRESHOLD and time_elapsed >= QUICK_TIME:
                # 策略2：10 条且 1 分钟
                should_write = True
                reason = f"积累 {len(batch)} 条且超过 {QUICK_TIME:.0f} 秒"
            elif time_elapsed >= MAX_WAIT_TIME:
                # 策略3：5 分钟必定写入
                should_write = True
                reason = f"超过最大等待时间 {MAX_WAIT_TIME:.0f} 秒"

            # 执行写入
            if should_write and batch:
                _process_user_activity_batch(batch)
                print(f"[动态策略] {reason}，批量写入")
                batch = []
                last_write_time = time.time()

        except Exception as e:
            print(f"[X] user_activity_writer 错误: {e}")

    # 线程结束前写入剩余数据
    if batch:
        _process_user_activity_batch(batch)
        print(f"[动态策略] 应用关闭，写入剩余 {len(batch)} 条记录")


def _process_user_activity_batch(batch: list):
    """批量处理用户活动更新（按用户聚合，避免重复写入）"""
    from app.auth.database import SessionLocal
    db = SessionLocal()

    try:
        # 按用户 ID 聚合更新（解决竞态条件）
        aggregated = defaultdict(lambda: {
            'total_seconds': 0,
            'last_timestamp': None,
            'session_start_time': None
        })

        for update in batch:
            user_data = aggregated[update.user_id]

            # 累加时长
            user_data['total_seconds'] += update.seconds_to_add

            # 保留最新的时间戳
            if update.update_last_seen:
                if user_data['last_timestamp'] is None or update.timestamp > user_data['last_timestamp']:
                    user_data['last_timestamp'] = update.timestamp

            # 保留最新的 session 起点
            if update.session_start_time:
                if user_data['session_start_time'] is None or update.session_start_time > user_data['session_start_time']:
                    user_data['session_start_time'] = update.session_start_time

        # 批量更新数据库
        for user_id, data in aggregated.items():
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if not user:
                continue

            # 累加在线时长
            if data['total_seconds'] > 0:
                user.total_online_seconds = (user.total_online_seconds or 0) + data['total_seconds']

            # 更新最后活跃时间
            if data['last_timestamp']:
                user.last_seen = data['last_timestamp']

            # 更新 session 起点
            if data['session_start_time']:
                user.current_session_started_at = data['session_start_time']

        db.commit()
        print(f"[OK] 批量更新 {len(aggregated)} 个用户的活动数据（处理了 {len(batch)} 条记录）")

    except Exception as e:
        print(f"[X] 用户活动批次失败: {e}")
        db.rollback()
    finally:
        db.close()


# === 启动/停止后台线程 ===
_activity_writer_started = False
_activity_writer_lock = threading.Lock()


def start_user_activity_writer():
    """启动用户活动更新后台线程"""
    global _activity_writer_started
    with _activity_writer_lock:
        if _activity_writer_started:
            return

        threading.Thread(target=user_activity_writer, daemon=True).start()
        _activity_writer_started = True
        print("[OK] 用户活动更新后台线程已启动")


def stop_user_activity_writer():
    """停止用户活动更新后台线程"""
    try:
        user_activity_queue.put_nowait(None)
    except:
        pass
    print("🛑 用户活动更新后台线程已停止")

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
def logout_user(db: Session, user: models.User) -> tuple[int, int]:
    """
    返回 (本次會話時長（秒）, 總在線時長（秒）)
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
    return session_secs, user.total_online_seconds


# --- 心跳 / 訪問受保護接口时更新 last_seen（并分段累加在线时长）---
def touch_activity(user: models.User) -> None:
    """
    记录用户活动（队列版本）
    - 不立即写数据库，放入队列异步处理
    - 解决竞态条件：队列中的更新会按用户聚合
    - 解决频繁写库：批量处理，减少数据库连接

    注意：此函数不再需要 db 参数，因为使用队列异步处理
    """
    now = utils.now_utc_naive()

    # 计算需要累加的时长
    seconds_to_add = 0
    if user.current_session_started_at:
        delta = now - user.current_session_started_at
        seg_secs = int(delta.total_seconds())

        # 如果时间差超过60分钟，视为新会话，不累加
        if seg_secs > 60 * 60:
            # 会话超时，重置 session 起点
            update = UserActivityUpdate(
                user_id=user.id,
                seconds_to_add=0,
                update_last_seen=True,
                session_start_time=now
            )
            user_activity_queue.put(update)
            return

        if seg_secs > 0:
            seconds_to_add = seg_secs

    # 放入队列（异步处理）
    update = UserActivityUpdate(
        user_id=user.id,
        seconds_to_add=seconds_to_add,
        update_last_seen=True,
        session_start_time=now
    )
    user_activity_queue.put(update)


def accumulate_online_time(user: models.User, seconds: int) -> None:
    """
    处理前端汇报的在线时长（队列版本）
    - 不立即写数据库，放入队列异步处理

    注意：此函数不再需要 db 参数，因为使用队列异步处理
    """
    if seconds <= 0:
        return

    # 放入队列（异步处理）
    update = UserActivityUpdate(
        user_id=user.id,
        seconds_to_add=seconds,
        update_last_seen=True,
        session_start_time=None
    )
    user_activity_queue.put(update)

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


# ===== Refresh Token Management =====
def store_refresh_token(
    db: Session,
    user_id: int,
    token: str,
    device_info: str = None
) -> models.RefreshToken:
    """Store refresh token in database"""
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Limit active refresh tokens per user
    active_tokens = db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user_id,
        models.RefreshToken.revoked == False,
        models.RefreshToken.expires_at > datetime.utcnow()
    ).count()

    if active_tokens >= MAX_ACTIVE_REFRESH_TOKENS:
        # Revoke oldest token
        oldest = db.query(models.RefreshToken).filter(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.revoked == False
        ).order_by(models.RefreshToken.created_at.asc()).first()
        if oldest:
            oldest.revoked = True

    refresh_token = models.RefreshToken(
        token=token,
        user_id=user_id,
        expires_at=expires_at,
        device_info=device_info
    )
    db.add(refresh_token)
    db.commit()
    return refresh_token


def validate_refresh_token(db: Session, token: str) -> models.RefreshToken | None:
    """Validate refresh token and return if valid"""
    refresh_token = db.query(models.RefreshToken).filter(
        models.RefreshToken.token == token,
        models.RefreshToken.revoked == False,
        models.RefreshToken.expires_at > datetime.utcnow()
    ).first()
    return refresh_token


def rotate_refresh_token(
    db: Session,
    old_token: models.RefreshToken
) -> tuple[str, models.RefreshToken]:
    """Rotate refresh token (revoke old, create new)"""
    new_token_str = utils.create_refresh_token()

    # Create new token
    new_token = models.RefreshToken(
        token=new_token_str,
        user_id=old_token.user_id,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        device_info=old_token.device_info
    )

    # Revoke old token
    old_token.revoked = True
    old_token.replaced_by = new_token_str

    db.add(new_token)
    db.commit()

    return new_token_str, new_token


def revoke_all_user_tokens(db: Session, user_id: int):
    """Revoke all refresh tokens for user (logout all devices)"""
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user_id,
        models.RefreshToken.revoked == False
    ).update({"revoked": True})
    db.commit()


def revoke_single_token(db: Session, token: str):
    """Revoke specific refresh token"""
    db.query(models.RefreshToken).filter(
        models.RefreshToken.token == token
    ).update({"revoked": True})
    db.commit()

