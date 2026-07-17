from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload

from app.service.auth.core.dependencies import (
    check_login_rate_limit,
    warn_legacy_token_without_session,
    _extract_auth_token,
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
from app.common.config import FRONTEND_VERIFY_EMAIL_URL
from app.common.auth_config import (
    REQUIRE_EMAIL_VERIFICATION,
    AUTH_COOKIE_NAME,
    AUTH_COOKIE_SECURE,
    AUTH_COOKIE_SAMESITE,
    AUTH_COOKIE_DOMAIN,
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_SECURE,
    REFRESH_COOKIE_SAMESITE,
    ACCESS_TOKEN_EXPIRE_SECONDS,
    REFRESH_TOKEN_EXPIRE_SECONDS,
)

router = APIRouter()
# Swagger 的 "Authorize" 按钮会用到这个 tokenUrl
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Web 登录/刷新成功后设置 HttpOnly Cookie"""
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        domain=AUTH_COOKIE_DOMAIN,
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_SECONDS,
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite=REFRESH_COOKIE_SAMESITE,
        domain=AUTH_COOKIE_DOMAIN,
        path="/",
        max_age=REFRESH_TOKEN_EXPIRE_SECONDS,
    )


def _clear_auth_cookies(response: Response) -> None:
    """注销时清除认证 Cookie"""
    # 同时清除新旧两种可能的 cookie name（防止配置变更后残留）
    for name in (AUTH_COOKIE_NAME, "access_token", REFRESH_COOKIE_NAME, "refresh_token"):
        response.delete_cookie(
            key=name,
            path="/",
            secure=AUTH_COOKIE_SECURE,
            samesite=AUTH_COOKIE_SAMESITE,
            domain=AUTH_COOKIE_DOMAIN,
        )


def _load_active_user_from_token(
    request: Request,
    db: Session,
    *,
    include_usage_summary: bool = False,
):
    """从请求中提取 token（支持 Authorization Bearer 和 HttpOnly Cookie），校验并加载用户"""
    token, __source = _extract_auth_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = utils.decode_access_token(token)
    except JWTError as e:
        print("JWTError:", e)
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    ver = payload.get("ver", 1)  # 无 ver 字段的旧 token 默认为 1（sub 是 username）
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token (no subject)")

    session_public_id = payload.get("session_id")
    if not session_public_id:
        warn_legacy_token_without_session(
            username=(sub if ver < 2 else None),
            source="_load_active_user_from_token",
        )
    if session_public_id and not get_valid_session_by_public_id(db, session_public_id):
        raise HTTPException(status_code=401, detail="Session is no longer active")

    query = db.query(models.User)
    if include_usage_summary:
        query = query.options(joinedload(models.User.usage_summary))

    # 新版 token（ver >= 2）：sub 是 user_id
    if ver >= 2:
        user = query.filter(models.User.id == int(sub)).first()
    else:
        user = query.filter(models.User.username == sub).first()
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
        "session_id": session_obj.session_id,
    }


def _raise_auth_conflict(
    message: str,
    *,
    conflict_code: str,
    suggested_action: str = service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
) -> None:
    raise HTTPException(
        status_code=409,
        detail=schemas.AuthConflictResponse(
            message=message,
            conflict_code=conflict_code,
            suggested_action=suggested_action,
        ).model_dump(),
    )


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
@router.post("/login")
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    client_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
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

    # Web 客户端：通过 HttpOnly Cookie 返回 token
    if client_type == "web":
        _set_auth_cookies(response, access_token, refresh_token)

    # 移动端 / 旧前端：通过 JSON 返回 token（web 也返回，前端忽略即可）
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_SECONDS,
    }
# Token refresh endpoint
@router.post("/refresh")
def refresh(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Body(None, embed=True),
    db: Session = Depends(get_db)
):
    """
    Exchange refresh token for new access + refresh token pair.
    Implements token rotation for security.

    Web 客户端：refresh_token 从 Cookie 读取（请求体可为空），成功后重新 Set-Cookie。
    移动端：refresh_token 从 JSON body 读取。
    """
    # Web：优先从 JSON body 读取，为空时从 Cookie 读取
    if not refresh_token:
        refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token required"
        )

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

        new_access_token = issue_access_token_for_session(token_obj.user, token_obj.session)
        # 刷新成功后重新 Set-Cookie（如果请求带了 Refresh Cookie 说明是 Web 客户端）
        if request.cookies.get(REFRESH_COOKIE_NAME):
            _set_auth_cookies(response, new_access_token, token_obj.token)

        return {
            "access_token": new_access_token,
            "refresh_token": token_obj.token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_SECONDS,
        }

    new_access_token, new_refresh_token = refresh_session(
        db=db,
        old_refresh_token=token_obj,
        ip_address=ip_address,
        device_info=device_info
    )

    # 刷新成功后重新 Set-Cookie（如果请求带了 Refresh Cookie 说明是 Web 客户端）
    if request.cookies.get(REFRESH_COOKIE_NAME):
        _set_auth_cookies(response, new_access_token, new_refresh_token)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_SECONDS,
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
        identity = service.change_primary_email(db, user, payload.new_email, current_password=payload.current_password)
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


@router.post("/register-email", response_model=schemas.MessageResponse)
def register_email(payload: schemas.EmailRegistrationStartRequest, request: Request, db: Session = Depends(get_db)):
    try:
        backend_verify_url = str(request.url_for("verify_email_registration")) + "?token=PLACEHOLDER"
        verify_url = service.build_action_url(FRONTEND_VERIFY_EMAIL_URL, "PLACEHOLDER", fallback_url=backend_verify_url)
        service.start_email_registration(
            db,
            email=payload.email,
            requested_ip=utils.extract_client_ip(request),
            verify_url=verify_url,
        )
        return {"message": "验证邮件已发送，请查收邮箱完成注册确认"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/verify-email-registration", name="verify_email_registration", response_model=schemas.EmailRegistrationVerifyResponse)
def verify_email_registration(token: str, db: Session = Depends(get_db)):
    try:
        return service.verify_email_registration_token(db, token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/complete-email-registration", response_model=schemas.EmailRegistrationAuthResponse)
def complete_email_registration(payload: schemas.EmailRegistrationCompleteRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user = service.complete_email_registration(
            db,
            token=payload.token,
            username=payload.username,
            password=payload.password,
            register_ip=utils.extract_client_ip(request),
        )
        tokens = _issue_session_tokens(db, user, request)
        return {
            "action": "register",
            "message": "邮箱注册并登录成功",
            "username": user.username,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "expires_in": tokens["expires_in"],
            "session_id": tokens["session_id"],
            "email": user.email,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset-password", response_model=schemas.MessageResponse)
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        service.reset_password_by_token(db, payload.token, payload.new_password)
        return {"message": "密码已重置，请重新登录"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/google/auth/start",
    response_model=schemas.OAuthStartResponse,
)
def google_auth_start(payload: schemas.OAuthStartRequest, request: Request, db: Session = Depends(get_db)):
    current_user = None
    if payload.intent == service.OAUTH_INTENT_BIND:
        raise HTTPException(status_code=401, detail="bind flow requires authenticated endpoint /google/bind/start")
    try:
        return service.start_google_oauth(
            db,
            intent=payload.intent,
            requested_ip=utils.extract_client_ip(request),
            redirect_uri=payload.redirect_uri,
            current_user=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/google/bind/start",
    response_model=schemas.OAuthStartResponse,
)
def google_bind_start(payload: schemas.OAuthStartRequest, request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, _ = _load_active_user_from_token(db, token)
    try:
        return service.start_google_oauth(
            db,
            intent=service.OAUTH_INTENT_BIND,
            requested_ip=utils.extract_client_ip(request),
            redirect_uri=payload.redirect_uri,
            current_user=user,
            current_session_public_id=payload.current_session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/google/auth/callback",
    response_model=schemas.GoogleAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def google_auth_callback(payload: schemas.OAuthCallbackRequest, db: Session = Depends(get_db)):
    if not payload.id_token:
        raise HTTPException(status_code=400, detail="id_token is required")
    try:
        return service.complete_google_oauth_callback(db, state=payload.state, id_token=payload.id_token)
    except service.AuthConflictError as e:
        _raise_auth_conflict(e.message, conflict_code=e.conflict_code, suggested_action=e.suggested_action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/google/auth",
    response_model=schemas.GoogleAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
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
            "session_id": tokens["session_id"],
            "email": google_payload.get("email"),
            "is_verified": True,
            "profile_picture": google_payload.get("picture"),
        }

    if result["action"] == "conflict":
        _raise_auth_conflict(
            "该 Google 邮箱已存在，请先用原账号登录后再绑定 Google",
            conflict_code=result.get("conflict_code") or service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS,
            suggested_action=result.get("suggested_action") or service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
        )

    return {
        "action": "register",
        "message": "Google 账号可用于注册，请补充用户名和密码完成创建",
        "email": google_payload.get("email"),
        "suggested_username": result.get("suggested_username"),
        "is_verified": bool(google_payload.get("email_verified")),
        "profile_picture": google_payload.get("picture"),
    }


@router.post(
    "/google/register",
    response_model=schemas.GoogleAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
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
            "session_id": tokens["session_id"],
            "email": identity.email,
            "is_verified": identity.is_verified,
            "profile_picture": identity.profile_picture,
        }
    except service.AuthConflictError as e:
        _raise_auth_conflict(e.message, conflict_code=e.conflict_code, suggested_action=e.suggested_action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/google/bind",
    response_model=schemas.GoogleAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def google_bind(payload: schemas.GoogleTokenRequest, request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, auth_payload = _load_active_user_from_token(db, token)
    try:
        identity = service.bind_google_identity(
            db,
            user,
            payload.id_token,
            current_session_public_id=auth_payload.get("session_id"),
        )
        return {
            "action": "bound",
            "message": "Google 账号绑定成功",
            "username": user.username,
            "provider": "google",
            "email": identity.email,
            "is_verified": identity.is_verified,
            "profile_picture": identity.profile_picture,
            "provider_subject": identity.provider_subject,
        }
    except service.AuthConflictError as e:
        _raise_auth_conflict(e.message, conflict_code=e.conflict_code, suggested_action=e.suggested_action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/google/rebind",
    response_model=schemas.GoogleAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def google_rebind(payload: schemas.GoogleTokenRequest, request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, auth_payload = _load_active_user_from_token(db, token)
    try:
        identity = service.rebind_google_identity(
            db,
            user,
            payload.id_token,
            current_session_public_id=auth_payload.get("session_id"),
        )
        return {
            "action": "bound",
            "message": "Google 账号换绑成功",
            "username": user.username,
            "provider": "google",
            "email": identity.email,
            "is_verified": identity.is_verified,
            "profile_picture": identity.profile_picture,
            "provider_subject": identity.provider_subject,
        }
    except service.AuthConflictError as e:
        _raise_auth_conflict(e.message, conflict_code=e.conflict_code, suggested_action=e.suggested_action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


"""TODO(auth-wechat-web): 旧微信网页 OAuth 路由暂保留在 auth.py，后续应拆到独立 web router。"""


@router.post(
    "/wechat/web/auth/start",
    response_model=schemas.OAuthStartResponse,
)
def wechat_auth_start(payload: schemas.OAuthStartRequest, request: Request, db: Session = Depends(get_db)):
    if payload.intent == service.OAUTH_INTENT_BIND:
        raise HTTPException(status_code=401, detail="bind flow requires authenticated endpoint /wechat/web/bind/start")
    try:
        return service.start_wechat_oauth(
            db,
            intent=payload.intent,
            requested_ip=utils.extract_client_ip(request),
            redirect_uri=payload.redirect_uri,
            current_user=None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/wechat/web/bind/start",
    response_model=schemas.OAuthStartResponse,
)
def wechat_bind_start(payload: schemas.OAuthStartRequest, request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, _ = _load_active_user_from_token(db, token)
    try:
        return service.start_wechat_oauth(
            db,
            intent=service.OAUTH_INTENT_BIND,
            requested_ip=utils.extract_client_ip(request),
            redirect_uri=payload.redirect_uri,
            current_user=user,
            current_session_public_id=payload.current_session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/wechat/web/auth/callback",
    response_model=schemas.WechatAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def wechat_auth_callback(payload: schemas.OAuthCallbackRequest, db: Session = Depends(get_db)):
    if not payload.access_token or not payload.openid:
        raise HTTPException(status_code=400, detail="access_token and openid are required")
    try:
        return service.complete_wechat_oauth_callback(
            db,
            state=payload.state,
            access_token=payload.access_token,
            openid=payload.openid,
        )
    except service.AuthConflictError as e:
        _raise_auth_conflict(e.message, conflict_code=e.conflict_code, suggested_action=e.suggested_action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/wechat/web/auth",
    response_model=schemas.WechatAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def wechat_auth(payload: schemas.WechatTokenRequest, request: Request, db: Session = Depends(get_db)):
    try:
        result = service.prepare_wechat_auth(db, payload.access_token, payload.openid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    wechat_payload = result["payload"]
    provider_subject = wechat_payload.get("unionid") or wechat_payload.get("openid")
    if result["action"] == "login":
        user = result["user"]
        wechat_identity = service.get_identity_by_provider_subject(db, "wechat", provider_subject)
        service.mark_user_login_success(db, user, login_ip=utils.extract_client_ip(request), identity=wechat_identity)
        tokens = _issue_session_tokens(db, user, request)
        return {
            "action": "login",
            "message": "微信登录成功",
            "username": user.username,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "expires_in": tokens["expires_in"],
            "session_id": tokens["session_id"],
            "profile_picture": wechat_payload.get("headimgurl"),
            "provider_subject": provider_subject,
        }

    if result["action"] == "conflict":
        _raise_auth_conflict(
            "该微信邮箱已存在，请先用原账号登录后再绑定微信",
            conflict_code=result.get("conflict_code") or service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS,
            suggested_action=result.get("suggested_action") or service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
        )

    return {
        "action": "register",
        "message": "微信账号可用于注册，请补充用户名和密码完成创建",
        "suggested_username": result.get("suggested_username"),
        "profile_picture": wechat_payload.get("headimgurl"),
        "provider_subject": provider_subject,
    }


@router.post(
    "/wechat/web/register",
    response_model=schemas.WechatAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def wechat_register(payload: schemas.WechatRegisterRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user, identity = service.register_user_with_wechat(db, payload, register_ip=utils.extract_client_ip(request))
        service.mark_user_login_success(db, user, login_ip=utils.extract_client_ip(request), identity=identity)
        tokens = _issue_session_tokens(db, user, request)
        return {
            "action": "login",
            "message": "微信注册并登录成功",
            "username": user.username,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "expires_in": tokens["expires_in"],
            "session_id": tokens["session_id"],
            "profile_picture": identity.profile_picture,
            "provider_subject": identity.provider_subject,
        }
    except service.AuthConflictError as e:
        _raise_auth_conflict(e.message, conflict_code=e.conflict_code, suggested_action=e.suggested_action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/wechat/web/bind",
    response_model=schemas.WechatAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def wechat_bind(payload: schemas.WechatTokenRequest, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, auth_payload = _load_active_user_from_token(db, token)
    try:
        identity = service.bind_wechat_identity(
            db,
            user,
            access_token=payload.access_token,
            openid=payload.openid,
            current_session_public_id=auth_payload.get("session_id"),
        )
        return {
            "action": "bound",
            "message": "微信账号绑定成功",
            "username": user.username,
            "provider": "wechat",
            "profile_picture": identity.profile_picture,
            "provider_subject": identity.provider_subject,
        }
    except service.AuthConflictError as e:
        _raise_auth_conflict(e.message, conflict_code=e.conflict_code, suggested_action=e.suggested_action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/providers", response_model=list[schemas.AuthProviderStatus])
def auth_providers(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, _ = _load_active_user_from_token(db, token)
    return service.list_auth_providers(db, user)


@router.delete("/providers/{provider}", response_model=schemas.AuthProviderMutationResponse)
def unbind_auth_provider(provider: str, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Legacy endpoint kept for compatibility; v1 policy is replace/rebind, not unlink."""
    user, _ = _load_active_user_from_token(db, token)
    try:
        service.unbind_auth_provider(db, user, provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "v1 仅支持换绑，不支持解绑",
        "providers": [schemas.AuthProviderStatus(**item) for item in service.list_auth_providers(db, user)],
    }


@router.post(
    "/wechat/web/rebind",
    response_model=schemas.WechatAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def wechat_rebind(payload: schemas.WechatTokenRequest, request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user, auth_payload = _load_active_user_from_token(db, token)
    try:
        identity = service.rebind_wechat_identity(
            db,
            user,
            payload.access_token,
            payload.openid,
            current_session_public_id=auth_payload.get("session_id"),
        )
        return {
            "action": "bound",
            "message": "微信账号换绑成功",
            "username": user.username,
            "provider": "wechat",
            "profile_picture": identity.profile_picture,
            "provider_subject": identity.provider_subject,
        }
    except service.AuthConflictError as e:
        _raise_auth_conflict(e.message, conflict_code=e.conflict_code, suggested_action=e.suggested_action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Me ==========
@router.get("/me", response_model=schemas.UserMeResponse)
def me(
    request: Request,
    db: Session = Depends(get_db),
    _swagger_auth: Optional[str] = Depends(oauth2_scheme),  # 仅用于 Swagger UI 生成 Authorize 按钮
):
    user, _ = _load_active_user_from_token(
        request,
        db,
        include_usage_summary=True,
    )
    payload = schemas.UserMeResponse.model_validate(user)
    payload.auth_providers = [schemas.AuthProviderStatus(**item) for item in service.list_auth_providers(db, user)]
    return payload


# ========== Logout ==========
@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Body(None),
    logout_all: bool = Body(False),
    db: Session = Depends(get_db),
    _swagger_auth: Optional[str] = Depends(oauth2_scheme),  # 仅用于 Swagger UI
):
    """Logout user and revoke tokens. Web 客户端会清除 Cookie。"""
    user, payload = _load_active_user_from_token(request, db)
    session_public_id = payload.get("session_id")
    current_session = (
        get_valid_session_by_public_id(db, session_public_id)
        if session_public_id else None
    )
    session_seconds = current_session.total_online_seconds if current_session else 0
    total_seconds = user.total_online_seconds or 0

    # 服务端撤销
    if logout_all:
        revoke_user_sessions(db, user.id, reason="logout_all")
        service.revoke_all_user_tokens(db, user.id)
    elif session_public_id:
        revoke_session_by_public_id(db, session_public_id, reason="logout")
    elif refresh_token:
        service.revoke_single_token(db, refresh_token)

    # 清除认证 Cookie
    _clear_auth_cookies(response)

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
    db: Session = Depends(get_db),
    _swagger_auth: Optional[str] = Depends(oauth2_scheme),  # 仅用于 Swagger UI
):
    user, payload = _load_active_user_from_token(request, db)
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
        'timestamp': utils.now_utc_naive()
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
    request: Request,
    username: str = Form(None),  # 使用 Form 获取数据
    email: str = Form(None),
    password: str = Form(None),
    new_password: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    _swagger_auth: Optional[str] = Depends(oauth2_scheme),  # 仅用于 Swagger UI
):
    current_user, _ = _load_active_user_from_token(request, db)

    try:
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/leaderboard", response_model=schemas.LeaderboardResponse)
def get_leaderboard(
    request: Request,
    db: Session = Depends(get_db),
    _swagger_auth: Optional[str] = Depends(oauth2_scheme),  # 仅用于 Swagger UI
):
    """
    Get comprehensive leaderboard rankings for current user.
    """
    user, _payload = _load_active_user_from_token(request, db)

    # Calculate all rankings
    from app.service.user.leaderboard_service import get_user_leaderboard
    return get_user_leaderboard(db, user.id)
