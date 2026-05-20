from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.routes import auth as auth_routes
from app.schemas import auth as schemas
from app.service.auth.core import service, utils, wechat_mini_service
from app.service.auth.database.connection import get_db

router = APIRouter()


@router.post(
    "/auth",
    response_model=schemas.WechatAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def wechat_mini_auth(payload: schemas.WechatMiniCodeRequest, request: Request, db: Session = Depends(get_db)):
    try:
        result = wechat_mini_service.prepare_wechat_mini_auth(db, payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    provider_subject = result["payload"].get("unionid") or result["payload"].get("openid")
    if result["action"] == "login":
        user = result["user"]
        identity = service.get_identity_by_provider_subject(db, wechat_mini_service.WECHAT_MINI_PROVIDER, provider_subject)
        service.mark_user_login_success(db, user, login_ip=utils.extract_client_ip(request), identity=identity)
        tokens = auth_routes._issue_session_tokens(db, user, request)
        return {
            "action": "login",
            "message": "微信小程序登录成功",
            "username": user.username,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "expires_in": tokens["expires_in"],
            "session_id": tokens["session_id"],
            "provider": wechat_mini_service.WECHAT_MINI_PROVIDER,
            "provider_subject": provider_subject,
        }

    return {
        "action": "register",
        "message": "微信小程序账号可用于注册，请补充用户名和密码完成创建",
        "suggested_username": result.get("suggested_username"),
        "provider": wechat_mini_service.WECHAT_MINI_PROVIDER,
        "provider_subject": provider_subject,
    }


@router.post(
    "/register",
    response_model=schemas.WechatAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def wechat_mini_register(payload: schemas.WechatMiniRegisterRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user, identity = wechat_mini_service.register_user_with_wechat_mini(
            db,
            payload,
            register_ip=utils.extract_client_ip(request),
        )
        service.mark_user_login_success(db, user, login_ip=utils.extract_client_ip(request), identity=identity)
        tokens = auth_routes._issue_session_tokens(db, user, request)
        return {
            "action": "login",
            "message": "微信小程序注册并登录成功",
            "username": user.username,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "expires_in": tokens["expires_in"],
            "session_id": tokens["session_id"],
            "provider": wechat_mini_service.WECHAT_MINI_PROVIDER,
            "provider_subject": identity.provider_subject,
        }
    except service.AuthConflictError as exc:
        auth_routes._raise_auth_conflict(exc.message, conflict_code=exc.conflict_code, suggested_action=exc.suggested_action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/bind",
    response_model=schemas.WechatAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def wechat_mini_bind(payload: schemas.WechatMiniCodeRequest, token: str = Depends(auth_routes.oauth2_scheme), db: Session = Depends(get_db)):
    user, auth_payload = auth_routes._load_active_user_from_token(db, token)
    try:
        identity = wechat_mini_service.bind_wechat_mini_identity(
            db,
            user,
            payload.code,
            current_session_public_id=auth_payload.get("session_id"),
        )
        return {
            "action": "bound",
            "message": "微信小程序账号绑定成功",
            "username": user.username,
            "provider": wechat_mini_service.WECHAT_MINI_PROVIDER,
            "provider_subject": identity.provider_subject,
        }
    except service.AuthConflictError as exc:
        auth_routes._raise_auth_conflict(exc.message, conflict_code=exc.conflict_code, suggested_action=exc.suggested_action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/rebind",
    response_model=schemas.WechatAuthResponse,
    responses={409: {"model": schemas.AuthConflictResponse}},
)
def wechat_mini_rebind(payload: schemas.WechatMiniCodeRequest, token: str = Depends(auth_routes.oauth2_scheme), db: Session = Depends(get_db)):
    user, auth_payload = auth_routes._load_active_user_from_token(db, token)
    try:
        identity = wechat_mini_service.rebind_wechat_mini_identity(
            db,
            user,
            payload.code,
            current_session_public_id=auth_payload.get("session_id"),
        )
        return {
            "action": "bound",
            "message": "微信小程序账号换绑成功",
            "username": user.username,
            "provider": wechat_mini_service.WECHAT_MINI_PROVIDER,
            "provider_subject": identity.provider_subject,
        }
    except service.AuthConflictError as exc:
        auth_routes._raise_auth_conflict(exc.message, conflict_code=exc.conflict_code, suggested_action=exc.suggested_action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
