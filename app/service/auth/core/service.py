from datetime import timedelta, datetime
from typing import Optional
import multiprocessing  # [FIX] 改用跨进程队列
import queue  # [FIX] 用于 queue.Empty 异常
import threading
import warnings
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.service.auth.core import utils
from app.service.auth.database import models
from app.schemas import auth as schemas
from app.common.config import REQUIRE_EMAIL_VERIFICATION, REGISTRATION_WINDOW_MINUTES, MAX_REGISTRATIONS_PER_IP, \
    REFRESH_TOKEN_EXPIRE_DAYS, MAX_ACTIVE_REFRESH_TOKENS, FRONTEND_RESET_PASSWORD_URL

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
    from app.service.auth.database.connection import SessionLocal
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


EMAIL_VERIFY_TOKEN_EXPIRE_MINUTES = 60 * 24
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 30


def get_primary_email_identity(db: Session, user_id: int) -> models.UserAuthIdentity | None:
    return db.query(models.UserAuthIdentity).filter(
        models.UserAuthIdentity.user_id == user_id,
        models.UserAuthIdentity.provider == "email",
        models.UserAuthIdentity.is_primary == True,
    ).first()


def get_identity_by_provider_subject(db: Session, provider: str, provider_subject: str) -> models.UserAuthIdentity | None:
    return db.query(models.UserAuthIdentity).filter(
        models.UserAuthIdentity.provider == provider,
        models.UserAuthIdentity.provider_subject == provider_subject,
    ).first()


def get_email_identity_by_normalized_email(db: Session, normalized_email: str) -> models.UserAuthIdentity | None:
    return db.query(models.UserAuthIdentity).filter(
        models.UserAuthIdentity.provider == "email",
        models.UserAuthIdentity.identifier_normalized == normalized_email,
    ).first()


def build_action_url(base_url: str | None, token: str, *, query_param: str = "token", fallback_url: str | None = None) -> str:
    if base_url:
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}{query_param}={token}"
    return fallback_url or token


def make_google_suggested_username(payload: dict) -> str:
    for raw in [payload.get("email"), payload.get("name"), payload.get("given_name")]:
        value = str(raw or "").strip()
        if not value:
            continue
        candidate = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
        candidate = candidate.strip("_")
        while "__" in candidate:
            candidate = candidate.replace("__", "_")
        if candidate:
            return candidate[:50]
    return f"google_{payload['sub'][:12]}"



def sync_user_email_projection(db: Session, user: models.User) -> models.User:
    identity = get_primary_email_identity(db, user.id)
    user.email = identity.email if identity else None
    if identity:
        user.is_verified = bool(identity.is_verified)
    return user



def ensure_email_identity(
    db: Session,
    user: models.User,
    email: str,
    *,
    is_verified: bool,
    is_primary: bool = True,
) -> models.UserAuthIdentity:
    normalized_email = utils.normalize_email(email)
    identity = get_primary_email_identity(db, user.id)
    if identity:
        identity.identifier_normalized = normalized_email
        identity.email = email
        identity.display_name = email
        identity.is_primary = is_primary
        identity.is_verified = bool(is_verified)
    else:
        identity = models.UserAuthIdentity(
            user_id=user.id,
            provider="email",
            provider_subject=None,
            identifier_normalized=normalized_email,
            email=email,
            display_name=email,
            is_verified=bool(is_verified),
            is_primary=is_primary,
        )
        db.add(identity)
        db.flush()

    sync_user_email_projection(db, user)
    return identity



def ensure_provider_identity(
    db: Session,
    *,
    user: models.User,
    provider: str,
    provider_subject: str,
    email: str | None = None,
    display_name: str | None = None,
    profile_picture: str | None = None,
    is_verified: bool = True,
) -> models.UserAuthIdentity:
    identity = get_identity_by_provider_subject(db, provider, provider_subject)
    if identity and identity.user_id != user.id:
        raise ValueError(f"{provider} identity already linked to another account")

    normalized_email = utils.normalize_email(email or "") or None
    if identity:
        identity.identifier_normalized = normalized_email
        identity.email = email
        identity.display_name = display_name or identity.display_name or email or provider
        identity.profile_picture = profile_picture or identity.profile_picture
        identity.is_verified = bool(is_verified)
    else:
        identity = models.UserAuthIdentity(
            user_id=user.id,
            provider=provider,
            provider_subject=provider_subject,
            identifier_normalized=normalized_email,
            email=email,
            display_name=display_name or email or provider,
            profile_picture=profile_picture,
            is_verified=bool(is_verified),
            is_primary=False,
        )
        db.add(identity)
        db.flush()

    identity.last_login_at = utils.now_utc_naive()
    return identity



def prepare_google_auth(db: Session, id_token: str) -> dict:
    payload = utils.verify_google_id_token(id_token)
    google_identity = get_identity_by_provider_subject(db, "google", payload["sub"])
    if google_identity and google_identity.user:
        google_identity.email = payload.get("email")
        google_identity.identifier_normalized = payload.get("email")
        google_identity.display_name = payload.get("name") or google_identity.display_name
        google_identity.profile_picture = payload.get("picture") or google_identity.profile_picture
        google_identity.is_verified = True
        sync_user_email_projection(db, google_identity.user)
        return {
            "action": "login",
            "user": google_identity.user,
            "payload": payload,
        }

    email = payload.get("email")
    if email:
        existing_email_identity = get_email_identity_by_normalized_email(db, email)
        if existing_email_identity and existing_email_identity.user:
            return {
                "action": "conflict",
                "conflict_code": "login_then_bind",
                "payload": payload,
                "existing_user": existing_email_identity.user,
            }

    return {
        "action": "register",
        "payload": payload,
        "suggested_username": make_google_suggested_username(payload),
    }



def register_user_with_google(db: Session, signup: schemas.GoogleRegisterRequest, register_ip: str) -> tuple[models.User, models.UserAuthIdentity]:
    payload = utils.verify_google_id_token(signup.id_token)
    if get_identity_by_provider_subject(db, "google", payload["sub"]):
        raise ValueError("Google account already linked")

    email = payload.get("email")
    if not email:
        raise ValueError("Google account did not provide email")

    existing_email_identity = get_email_identity_by_normalized_email(db, email)
    if existing_email_identity:
        raise ValueError("Email already exists, please login and bind Google first")

    user = register_user(
        db,
        schemas.UserCreate(username=signup.username, email=email, password=signup.password),
        register_ip=register_ip,
    )
    email_identity = ensure_email_identity(db, user, email, is_verified=bool(payload.get("email_verified")), is_primary=True)
    google_identity = ensure_provider_identity(
        db,
        user=user,
        provider="google",
        provider_subject=payload["sub"],
        email=email,
        display_name=payload.get("name"),
        profile_picture=payload.get("picture"),
        is_verified=True,
    )
    if payload.get("picture"):
        user.profile_picture = payload.get("picture")
    sync_user_email_projection(db, user)
    db.commit()
    db.refresh(user)
    db.refresh(google_identity)
    db.refresh(email_identity)
    return user, google_identity



def bind_google_identity(db: Session, user: models.User, id_token: str) -> models.UserAuthIdentity:
    payload = utils.verify_google_id_token(id_token)
    existing_google_identity = get_identity_by_provider_subject(db, "google", payload["sub"])
    if existing_google_identity and existing_google_identity.user_id != user.id:
        raise ValueError("Google account already linked to another account")

    current_google_identity = db.query(models.UserAuthIdentity).filter(
        models.UserAuthIdentity.user_id == user.id,
        models.UserAuthIdentity.provider == "google",
    ).first()
    if current_google_identity and current_google_identity.provider_subject != payload["sub"]:
        raise ValueError("Current account already linked to another Google account")

    identity = ensure_provider_identity(
        db,
        user=user,
        provider="google",
        provider_subject=payload["sub"],
        email=payload.get("email"),
        display_name=payload.get("name"),
        profile_picture=payload.get("picture"),
        is_verified=True,
    )
    if payload.get("picture") and not user.profile_picture:
        user.profile_picture = payload.get("picture")
    db.commit()
    db.refresh(identity)
    return identity



def issue_auth_action_token(
    db: Session,
    *,
    user: models.User,
    action: str,
    identity: models.UserAuthIdentity | None = None,
    requested_ip: str | None = None,
    expires_minutes: int,
) -> str:
    token = utils.create_opaque_token()
    token_hash = utils.hash_opaque_token(token)

    db.query(models.AuthActionToken).filter(
        models.AuthActionToken.user_id == user.id,
        models.AuthActionToken.action == action,
        models.AuthActionToken.consumed_at.is_(None),
    ).delete(synchronize_session=False)

    db.add(models.AuthActionToken(
        user_id=user.id,
        identity_id=identity.id if identity else None,
        action=action,
        token_hash=token_hash,
        requested_ip=requested_ip,
        expires_at=utils.now_utc_naive() + timedelta(minutes=expires_minutes),
    ))
    db.flush()
    return token



def issue_email_verification_token(db: Session, user: models.User, requested_ip: str | None = None) -> tuple[str, models.UserAuthIdentity]:
    identity = get_primary_email_identity(db, user.id)
    if not identity or not identity.email:
        raise ValueError("当前账号没有可验证的邮箱身份")
    token = issue_auth_action_token(
        db,
        user=user,
        action="verify_email",
        identity=identity,
        requested_ip=requested_ip,
        expires_minutes=EMAIL_VERIFY_TOKEN_EXPIRE_MINUTES,
    )
    return token, identity



def verify_email_token(db: Session, token: str) -> models.User:
    token_hash = utils.hash_opaque_token(token)
    record = db.query(models.AuthActionToken).filter(
        models.AuthActionToken.action == "verify_email",
        models.AuthActionToken.token_hash == token_hash,
    ).first()
    if not record or record.consumed_at is not None or record.expires_at <= utils.now_utc_naive():
        raise ValueError("Invalid or expired token")
    if not record.user or not record.identity:
        raise ValueError("Verification token is malformed")

    record.identity.is_verified = True
    record.consumed_at = utils.now_utc_naive()
    sync_user_email_projection(db, record.user)
    db.commit()
    db.refresh(record.user)
    return record.user



def send_verification_email(user: models.User, email: str, verify_url: str) -> None:
    body = (
        f"你好 {user.username}，\n\n"
        f"请点击下面的链接完成邮箱验证：\n{verify_url}\n\n"
        f"链接 24 小时内有效。"
    )
    html = (
        f"<p>你好 {user.username}，</p>"
        f"<p>请点击下面的链接完成邮箱验证：</p>"
        f"<p><a href=\"{verify_url}\">验证邮箱</a></p>"
        f"<p>链接 24 小时内有效。</p>"
    )
    utils.send_email(email=email, subject="请验证你的邮箱", body=body, html=html)



def send_password_reset_email(user: models.User, email: str, token: str) -> None:
    reset_url = build_action_url(FRONTEND_RESET_PASSWORD_URL, token)
    body = (
        f"你好 {user.username}，\n\n"
        f"你正在请求重置密码。\n"
        f"请打开下面的链接重置密码：\n{reset_url}\n\n"
        f"如果你的前端还未接好，也可以直接使用 token：\n{token}\n\n"
        f"该链接 / token 30 分钟内有效。"
    )
    html = (
        f"<p>你好 {user.username}，</p>"
        f"<p>你正在请求重置密码。</p>"
        f"<p><a href=\"{reset_url}\">重置密码</a></p>"
        f"<p>如果前端还未接好，也可以直接使用 token：</p>"
        f"<pre>{token}</pre>"
        f"<p>该链接 / token 30 分钟内有效。</p>"
    )
    utils.send_email(email=email, subject="重置密码", body=body, html=html)



def request_password_reset(db: Session, email: str, requested_ip: str | None = None) -> bool:
    normalized_email = utils.normalize_email(email)
    identity = db.query(models.UserAuthIdentity).filter(
        models.UserAuthIdentity.provider == "email",
        models.UserAuthIdentity.identifier_normalized == normalized_email,
    ).first()
    if not identity or not identity.user:
        return False

    token = issue_auth_action_token(
        db,
        user=identity.user,
        action="reset_password",
        identity=identity,
        requested_ip=requested_ip,
        expires_minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
    )
    send_password_reset_email(identity.user, identity.email or email, token)
    db.commit()
    return True



def reset_password_by_token(db: Session, token: str, new_password: str) -> models.User:
    token_hash = utils.hash_opaque_token(token)
    record = db.query(models.AuthActionToken).filter(
        models.AuthActionToken.action == "reset_password",
        models.AuthActionToken.token_hash == token_hash,
    ).first()
    if not record or record.consumed_at is not None or record.expires_at <= utils.now_utc_naive():
        raise ValueError("Invalid or expired token")
    if not record.user:
        raise ValueError("Reset token is malformed")

    record.user.hashed_password = utils.get_password_hash(new_password)
    record.user.failed_attempts = 0
    record.user.last_failed_login = None
    record.consumed_at = utils.now_utc_naive()
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == record.user_id,
        models.RefreshToken.revoked == False,
    ).update({"revoked": True}, synchronize_session=False)
    db.query(models.Session).filter(
        models.Session.user_id == record.user_id,
        models.Session.revoked == False,
    ).update({
        "revoked": True,
        "revoked_reason": "password_reset",
        "revoked_at": utils.now_utc_naive(),
    }, synchronize_session=False)
    db.commit()
    db.refresh(record.user)
    return record.user



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

    normalized_email = utils.normalize_email(user.email)

    # 檢查帳號是否存在
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise ValueError("Username already exists")
    if db.query(models.UserAuthIdentity).filter(
        models.UserAuthIdentity.provider == "email",
        models.UserAuthIdentity.identifier_normalized == normalized_email,
    ).first():
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
    db.flush()
    ensure_email_identity(
        db,
        db_user,
        user.email,
        is_verified=not REQUIRE_EMAIL_VERIFICATION,
        is_primary=True,
    )
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, username: str, password: str, login_ip: str) -> models.User:
    user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    email_identity = None
    if not user and "@" in username:
        normalized_email = utils.normalize_email(username)
        email_identity = db.query(models.UserAuthIdentity).filter(
            models.UserAuthIdentity.provider == "email",
            models.UserAuthIdentity.identifier_normalized == normalized_email,
        ).first()
        if email_identity:
            user = email_identity.user

    if not user:
        # 不暴露用户存在性
        raise ValueError("Invalid credentials")

    if not email_identity:
        email_identity = get_primary_email_identity(db, user.id)

    if not utils.verify_password(password, user.hashed_password):
        user.failed_attempts = (user.failed_attempts or 0) + 1
        user.last_failed_login = utils.now_utc_naive()
        db.commit()
        raise ValueError("Invalid credentials")

    # 未验证则阻断（注意：此时不应更新 last_login 等字段）
    if REQUIRE_EMAIL_VERIFICATION and email_identity and not email_identity.is_verified:
        raise PermissionError("Email not verified")

    mark_user_login_success(db, user, login_ip=login_ip, identity=email_identity)
    return user



def mark_user_login_success(
    db: Session,
    user: models.User,
    *,
    login_ip: str,
    identity: models.UserAuthIdentity | None = None,
) -> models.User:
    sync_user_email_projection(db, user)
    user.failed_attempts = 0
    user.last_login = utils.now_utc_naive()
    user.last_login_ip = login_ip
    user.login_count = (user.login_count or 0) + 1
    user.current_session_started_at = user.last_login
    user.last_seen = user.last_login
    if identity:
        identity.last_login_at = user.last_login
    db.commit()
    db.refresh(user)
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
    warnings.warn(
        "issue_token_for_user issues a legacy access token without session_id; "
        "prefer create_session() or issue_access_token_for_session().",
        DeprecationWarning,
        stacklevel=2,
    )
    return utils.create_access_token(subject=user.username, expires_minutes=minutes)


def update_user_profile(
        db: Session,
        user_id: int,  # 仅允许更新当前登录用户
        username: Optional[str] = None,  # 用户名可选
        password: Optional[str] = None,  # 当前密码可选
        new_password: Optional[str] = None,  # 新密码可选
) -> models.User:
    # 查询当前登录用户
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用戶未找到")

    # 如果提供了当前密码（并且要修改密码），则验证当前密码
    if new_password and not password:
        raise HTTPException(status_code=400, detail="修改密碼時需要提供當前密碼")

    if password and not utils.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="當前密碼錯誤")

    # 如果提供了新的用户名，则修改用户名
    if username:
        # 允许保持原用户名，只有变更时才检查唯一性
        if username != user.username:
            existing_user = db.query(models.User).filter(
                models.User.username == username,
                models.User.id != user.id
            ).first()
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
