from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session, joinedload

from app.service.auth.core.dependencies import (
    check_login_rate_limit,
    warn_legacy_token_without_session,
)
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
from app.common.config import REQUIRE_EMAIL_VERIFICATION, FRONTEND_VERIFY_EMAIL_URL

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
    if not session_public_id:
        warn_legacy_token_without_session(
            username=username,
            source="_load_active_user_from_token",
        )
    if session_public_id and not get_valid_session_by_public_id(db, session_public_id):
        raise HTTPException(status_code=401, detail="Session is no longer active")

    query = db.query(models.User)
    if include_usage_summary:
        query = query.options(joinedload(models.User.usage_summary))

    user = query.filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user, payload



def _issue_session_tokens(db: Session, user: models.User, request: Request) -> dict:
    session_obj, access_token, refresh_token = create_session(
        db=db,
        user=user,
        device_info=request.headers.get("User-Agent", "Unknown"),
        ip_address=utils.extract_client_ip(request),
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 30 * 60,
        "session_id": session_obj.public_id,
    }


# 注册：根据开关决定是否要求邮箱验证；生成验证链接并发送
@router.post("/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    client_ip = utils.extract_client_ip(request)
    try:
        created = service.register_user(db, user, register_ip=client_ip)

        if REQUIRE_EMAIL_VERIFICATION and created.email:
            token, identity = service.issue_email_verification_token(db, created, requested_ip=client_ip)
            backend_verify_url = str(request.url_for("verify_email")) + f"?token={token}"
            verify_url = service.build_action_url(FRONTEND_VERIFY_EMAIL_URL, token, fallback_url=backend_verify_url)
            service.send_verification_email(created, identity.email or created.email, verify_url)
            db.commit()

        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


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
@router.get("/verify-email", name="verify_email", response_model=schemas.MessageResponse)
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        user = service.verify_email_token(db, token)
        return {"message": f"邮箱验证成功：{user.username}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resend-verification", response_model=schemas.MessageResponse)
def resend_verification(payload: schemas.EmailRequest, request: Request, db: Session = Depends(get_db)):
    normalized_email = utils.normalize_email(payload.email)
    identity = db.query(models.UserAuthIdentity).filter(
        models.UserAuthIdentity.provider == "email",
        models.UserAuthIdentity.identifier_normalized == normalized_email,
    ).first()
    if not identity or not identity.user:
        return {"message": "如果邮箱存在，验证邮件已重新发送"}
    if identity.is_verified:
        return {"message": "该邮箱已经完成验证"}

    try:
        token, _ = service.issue_email_verification_token(db, identity.user, requested_ip=utils.extract_client_ip(request))
        backend_verify_url = str(request.url_for("verify_email")) + f"?token={token}"
        verify_url = service.build_action_url(FRONTEND_VERIFY_EMAIL_URL, token, fallback_url=backend_verify_url)
        service.send_verification_email(identity.user, identity.email or payload.email, verify_url)
        db.commit()
        return {"message": "验证邮件已发送"}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/change-email", response_model=schemas.ChangeEmailResponse)
def change_email(payload: schemas.ChangeEmailRequest, request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, _ = _load_active_user_from_token(db, token)
    try:
        identity = service.change_primary_email(db, user, payload.new_email)
        verify_token, _ = service.issue_email_verification_token(db, user, requested_ip=utils.extract_client_ip(request))
        backend_verify_url = str(request.url_for("verify_email")) + f"?token={verify_token}"
        verify_url = service.build_action_url(FRONTEND_VERIFY_EMAIL_URL, verify_token, fallback_url=backend_verify_url)
        service.send_verification_email(user, identity.email or payload.new_email, verify_url)
        db.commit()
        return {
            "message": "邮箱已更新，请查收新邮箱并完成验证",
            "email": identity.email,
            "is_verified": bool(identity.is_verified),
            "providers": [schemas.AuthProviderStatus(**item) for item in service.list_auth_providers(db, user)],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/change-password", response_model=schemas.ChangePasswordResponse)
def change_password(payload: schemas.ChangePasswordRequest, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, auth_payload = _load_active_user_from_token(db, token)
    try:
        service.change_password(
            db,
            user,
            current_password=payload.current_password,
            new_password=payload.new_password,
            revoke_other_sessions=payload.revoke_other_sessions,
            current_session_public_id=auth_payload.get("session_id"),
        )
        return {
            "message": "密码修改成功",
            "revoked_other_sessions": bool(payload.revoke_other_sessions),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/forgot-password", response_model=schemas.MessageResponse)
def forgot_password(payload: schemas.EmailRequest, request: Request, db: Session = Depends(get_db)):
    try:
        service.request_password_reset(db, payload.email, requested_ip=utils.extract_client_ip(request))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"message": "如果邮箱存在，重置密码邮件已发送"}


@router.post("/reset-password", response_model=schemas.MessageResponse)
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        service.reset_password_by_token(db, payload.token, payload.new_password)
        return {"message": "密码已重置，请重新登录"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/google/auth", response_model=schemas.GoogleAuthResponse)
def google_auth(payload: schemas.GoogleTokenRequest, request: Request, db: Session = Depends(get_db)):
    try:
        result = service.prepare_google_auth(db, payload.id_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    google_payload = result["payload"]
    if result["action"] == "login":
        user = result["user"]
        google_identity = service.get_identity_by_provider_subject(db, "google", google_payload["sub"])
        service.mark_user_login_success(db, user, login_ip=utils.extract_client_ip(request), identity=google_identity)
        tokens = _issue_session_tokens(db, user, request)
        return {
            "action": "login",
            "message": "Google 登录成功",
            "username": user.username,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "expires_in": tokens["expires_in"],
            "email": google_payload.get("email"),
            "is_verified": True,
            "profile_picture": google_payload.get("picture"),
        }

    if result["action"] == "conflict":
        return {
            "action": "conflict",
            "message": "该 Google 邮箱已存在，请先用原账号登录后再绑定 Google",
            "email": google_payload.get("email"),
            "conflict_code": result.get("conflict_code"),
            "is_verified": bool(google_payload.get("email_verified")),
            "profile_picture": google_payload.get("picture"),
        }

    return {
        "action": "register",
        "message": "Google 账号可用于注册，请补充用户名和密码完成创建",
        "email": google_payload.get("email"),
        "suggested_username": result.get("suggested_username"),
        "is_verified": bool(google_payload.get("email_verified")),
        "profile_picture": google_payload.get("picture"),
    }


@router.post("/google/register", response_model=schemas.GoogleAuthResponse)
def google_register(payload: schemas.GoogleRegisterRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user, identity = service.register_user_with_google(db, payload, register_ip=utils.extract_client_ip(request))
        service.mark_user_login_success(db, user, login_ip=utils.extract_client_ip(request), identity=identity)
        tokens = _issue_session_tokens(db, user, request)
        return {
            "action": "login",
            "message": "Google 注册并登录成功",
            "username": user.username,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "expires_in": tokens["expires_in"],
            "email": identity.email,
            "is_verified": identity.is_verified,
            "profile_picture": identity.profile_picture,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise


@router.post("/google/bind", response_model=schemas.GoogleAuthResponse)
def google_bind(payload: schemas.GoogleTokenRequest, request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, _ = _load_active_user_from_token(db, token)
    try:
        identity = service.bind_google_identity(db, user, payload.id_token)
        return {
            "action": "bind",
            "message": "Google 账号绑定成功",
            "username": user.username,
            "email": identity.email,
            "is_verified": identity.is_verified,
            "profile_picture": identity.profile_picture,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/providers", response_model=list[schemas.AuthProviderStatus])
def auth_providers(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, _ = _load_active_user_from_token(db, token)
    return service.list_auth_providers(db, user)


@router.delete("/providers/{provider}", response_model=schemas.AuthProviderMutationResponse)
def unbind_auth_provider(provider: str, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, _ = _load_active_user_from_token(db, token)
    try:
        providers = service.unbind_auth_provider(db, user, provider)
        return {
            "message": f"{provider} 绑定已解除",
            "providers": [schemas.AuthProviderStatus(**item) for item in providers],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Me（恢复 & 最小化改动）==========
@router.get("/me", response_model=schemas.UserMeResponse)
def me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, _ = _load_active_user_from_token(
        db,
        token,
        include_usage_summary=True,
    )
    payload = schemas.UserMeResponse.model_validate(user)
    payload.auth_providers = [schemas.AuthProviderStatus(**item) for item in service.list_auth_providers(db, user)]
    return payload


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
    from app.service.logging.stats.online_time_pipeline import enqueue_online_time_non_blocking
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
