from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session, joinedload

from app.service.auth.core.dependencies import check_login_rate_limit
from app.service.auth.core import utils
from app.service.auth.core.service import update_user_profile, models
from app.service.auth.session.service import (
    create_session,
    get_valid_session_by_public_id,
    issue_access_token_for_session,
    refresh_session,
    resolve_refresh_token_for_exchange,
    revoke_session_by_public_id,
    revoke_user_sessions,
)
from app.service.auth.session.online_time_guard import check_online_time_report_limits
from app.schemas import auth as schemas
from app.service.auth.core import service
from app.service.auth.database.connection import get_db
from app.common.config import REQUIRE_EMAIL_VERIFICATION

router = APIRouter()
# Swagger 的 "Authorize" 按钮会用到这个 tokenUrl
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _load_active_user_from_token(
    db: Session,
    token: str,
    *,
    include_usage_summary: bool = False,
):
    try:
        payload = utils.decode_access_token(token)
    except JWTError as e:
        print("JWTError:", e)
        raise HTTPException(status_code=401, detail="Invalid token")

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token (no subject)")

    session_public_id = payload.get("session_id")
    if session_public_id and not get_valid_session_by_public_id(db, session_public_id):
        raise HTTPException(status_code=401, detail="Session is no longer active")

    query = db.query(models.User)
    if include_usage_summary:
        query = query.options(joinedload(models.User.usage_summary))

    user = query.filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user, payload


# 注册：根据开关决定是否要求邮箱验证；生成验证链接并发送
@router.post("/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    client_ip = utils.extract_client_ip(request)
    try:
        created = service.register_user(db, user, register_ip=client_ip)

        if REQUIRE_EMAIL_VERIFICATION:
            # 以 email 做 subject，设置 24h 过期
            token = utils.create_access_token(subject=created.email, expires_minutes=60 * 24)
            # 使用 url_for 生成你的后端地址（避免硬编码域名）
            verify_url = str(request.url_for("verify_email")) + f"?token={token}"
            utils.send_email(
                email=created.email,
                subject="Verify your email",
                body=f"Hello {created.username},\n\nPlease verify your email by clicking the link below:\n{verify_url}\n\nThis link expires in 24 hours.",
            )

        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 登录：未验证时返回 403；其它无效凭证返回 401
@router.post("/login", response_model=schemas.TokenPair)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    client_ip = utils.extract_client_ip(request)

    # [OK] 檢查 IP 是否超過登入次數限制
    check_login_rate_limit(db, client_ip)
    try:
        user = service.authenticate_user(db, form_data.username, form_data.password, login_ip=client_ip)
    except PermissionError:
        # [X] 驗證失敗也記 log
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    device_info = request.headers.get("User-Agent", "Unknown")
    ip_address = client_ip

    session_obj, access_token, refresh_token = create_session(
        db=db,
        user=user,
        device_info=device_info,
        ip_address=ip_address
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 30 * 60  # 30 minutes in seconds
    }
# Token refresh endpoint
@router.post("/refresh", response_model=schemas.TokenPair)
def refresh(
    request: Request,
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    Exchange refresh token for new access + refresh token pair.
    Implements token rotation for security.
    """
    ip_address = utils.extract_client_ip(request)
    device_info = request.headers.get("User-Agent", "Unknown")

    token_obj, reused = resolve_refresh_token_for_exchange(
        db,
        refresh_token,
        ip_address=ip_address,
        device_info=device_info,
    )
    if not token_obj:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )

    if reused:
        if not token_obj.session or not token_obj.user:
            raise HTTPException(
                status_code=401,
                detail="Refresh token session is invalid"
            )

        return {
            "access_token": issue_access_token_for_session(token_obj.user, token_obj.session),
            "refresh_token": token_obj.token,
            "token_type": "bearer",
            "expires_in": 30 * 60
        }

    new_access_token, new_refresh_token = refresh_session(
        db=db,
        old_refresh_token=token_obj,
        ip_address=ip_address,
        device_info=device_info
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": 30 * 60  # 30 minutes in seconds
    }


# 邮箱验证：点击邮件中的链接来到这里
@router.get("/verify-email", name="verify_email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """
    暫時不用這個函數。
    :param token:
    :param db:
    :return:
    """
    try:
        payload = utils.decode_access_token(token)
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid token payload")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email already verified"}

    user.is_verified = True
    db.commit()
    return {"message": "Email verified successfully"}


# ========== Me（恢复 & 最小化改动）==========
@router.get("/me", response_model=schemas.UserMeResponse)
def me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, _ = _load_active_user_from_token(
        db,
        token,
        include_usage_summary=True,
    )
    return user
    try:
        payload = utils.decode_access_token(token)  # 解码 token
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token (no subject)")
    except JWTError as e:
        print("JWTError:", e)  # 临时日志
        # 如果 token 过期了，给出明确的错误信息
        raise HTTPException(status_code=401, detail="Token 已過期，請重新登錄")

    user = db.query(models.User) \
        .options(joinedload(models.User.usage_summary)) \
        .filter(models.User.username == username) \
        .first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 刷新活跃时间（统计在线时长时有用）
    # service.touch_activity(user)  # 已废弃，使用 /api/auth/report-activity 代替
    return user


# ========== Logout ==========
@router.post("/logout", response_model=schemas.LogoutResponse)
def logout(
    token: str = Depends(oauth2_scheme),
    refresh_token: Optional[str] = Body(None),
    logout_all: bool = Body(False),
    db: Session = Depends(get_db)
):
    """Logout user and revoke tokens"""
    user, payload = _load_active_user_from_token(db, token)
    session_public_id = payload.get("session_id")
    current_session = (
        get_valid_session_by_public_id(db, session_public_id)
        if session_public_id else None
    )
    session_seconds = current_session.total_online_seconds if current_session else 0
    total_seconds = user.total_online_seconds or 0

    # Revoke tokens
    if logout_all:
        revoke_user_sessions(db, user.id, reason="logout_all")
        service.revoke_all_user_tokens(db, user.id)
    elif session_public_id:
        revoke_session_by_public_id(db, session_public_id, reason="logout")
    elif refresh_token:
        service.revoke_single_token(db, refresh_token)

    return {
        "message": "Logout successful",
        "session_seconds": session_seconds,
        "total_online_seconds": total_seconds
    }


# ========== Report Online Time ==========
@router.post("/report-online-time")
def report_online_time(
    request: Request,
    seconds: int = Body(..., embed=True, ge=1, le=3600),  # 1秒到1小时
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    user, payload = _load_active_user_from_token(db, token)
    session_id = payload.get("session_id")
    ip_address = utils.extract_client_ip(request)

    """
    前端上报在线时长（使用队列实现非阻塞写入）

    前端应该：
    1. 使用 Page Visibility API 监听页面可见性
    2. 当页面可见时开始计时
    3. 当页面不可见或定期（如每分钟）上报累计时长

    参数：
    - seconds: 本次上报的在线时长（秒），范围 1-3600

    返回：
    - success: 是否成功
    - reported_seconds: 本次上报的秒数
    - total_online_seconds: 用户总在线时长（秒，可能略有延迟）
    """
    allowed, limit_detail = check_online_time_report_limits(
        session_id=session_id,
        user_id=user.id,
        ip_address=ip_address,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail=limit_detail)

    # Queue the accepted heartbeat; persistence remains asynchronous.
    from app.service.logging.middleware.traffic_logging import enqueue_online_time_non_blocking
    accepted = enqueue_online_time_non_blocking({
        'user_id': user.id,
        'session_id': session_id,
        'seconds': seconds,
        'timestamp': datetime.utcnow()
    })
    if not accepted:
        raise HTTPException(
            status_code=503,
            detail="Online time tracker is busy, please retry shortly",
        )

    # Return immediately (non-blocking)
    return {
        "success": True,
        "reported_seconds": seconds,
        "total_online_seconds": user.total_online_seconds or 0  # May be slightly stale
    }


@router.put("/updateProfile")
async def update_profile(
    username: str = Form(None),  # 使用 Form 获取数据
    email: str = Form(None),
    password: str = Form(None),
    new_password: Optional[str] = Form(None),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user, _ = _load_active_user_from_token(db, token)

    try:
        payload = utils.decode_access_token(token)
        token_username = payload.get("sub")
        if not token_username:
            raise HTTPException(status_code=401, detail="Invalid token")

        current_user = db.query(models.User).filter(models.User.username == token_username).first()
        if not current_user:
            raise HTTPException(status_code=404, detail="User not found")

        # 防止通过表单 email 指向他人账号（兼容旧前端保留字段）
        if email and email != current_user.email:
            raise HTTPException(status_code=403, detail="只能修改自己的帳號資料")

        updated_user = update_user_profile(
            db=db,
            user_id=current_user.id,
            username=username,
            password=password,
            new_password=new_password
        )
        return {" message": "用戶資料更新成功!", "user": {"username": updated_user.username, "email": updated_user.email}}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/leaderboard", response_model=schemas.LeaderboardResponse)
def get_leaderboard(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    user, _ = _load_active_user_from_token(db, token)

    """
    Get comprehensive leaderboard rankings for current user.

    Returns category, grouped, and endpoint ranking metrics in a single response:
    - online_time: Total online time ranking
    - total_queries: Total API queries ranking
    - category_音韻查詢: Phonology queries category
    - category_字調查詢: Character/tone queries category
    - category_音系分析: System analysis category
    - category_工具使用: Tools usage category
    - category_其他查询: Other queries category, including villagesML aggregate
    - endpoint_group_villages_ml: Aggregated villagesML ranking
    - endpoint_group_pho_pie: Aggregated pho_pie ranking
    - endpoint_*: Individual endpoint rankings

    Each ranking includes:
    - rank: User's rank (null if no activity)
    - value: User's value for this metric
    - gap_to_prev: Gap to previous rank (null for rank 1)
    - first_place_value: First place user's value
    """
    try:
        payload = utils.decode_access_token(token)
        username = payload.get("sub")

        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate all rankings
    from app.service.user.leaderboard_service import get_user_leaderboard
    return get_user_leaderboard(db, user.id)
