from sqlalchemy.orm import Session

from app.schemas import auth as schemas
from app.service.auth.core import service, utils
from app.service.auth.core.wechat_mini_client import (
    WechatMiniClientError,
    exchange_code_for_session,
)
from app.service.auth.database import models

WECHAT_MINI_PROVIDER = "wechat_mini"


def _load_wechat_mini_payload(code: str) -> dict:
    try:
        return exchange_code_for_session(code)
    except WechatMiniClientError as exc:
        raise ValueError(str(exc)) from exc


def prepare_wechat_mini_auth(db: Session, code: str) -> dict:
    payload = _load_wechat_mini_payload(code)
    provider_subject = payload.get("unionid") or payload["openid"]
    identity = service.get_identity_by_provider_subject(db, WECHAT_MINI_PROVIDER, provider_subject)
    if identity and identity.user:
        identity.identifier_normalized = payload.get("openid")
        identity.is_verified = True
        return {
            "action": "login",
            "user": identity.user,
            "payload": payload,
        }

    return {
        "action": "register",
        "payload": payload,
        "suggested_username": service.make_wechat_suggested_username(payload),
    }


def register_user_with_wechat_mini(
    db: Session,
    signup: schemas.WechatMiniRegisterRequest,
    register_ip: str,
) -> tuple[models.User, models.UserAuthIdentity]:
    payload = _load_wechat_mini_payload(signup.code)
    provider_subject = payload.get("unionid") or payload["openid"]
    if service.get_identity_by_provider_subject(db, WECHAT_MINI_PROVIDER, provider_subject):
        raise service.AuthConflictError(
            "WeChat Mini account already linked",
            conflict_code=service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED,
        )

    if db.query(models.User).filter(models.User.username == signup.username).first():
        raise ValueError("Username already exists")

    now = utils.now_utc_naive()
    user = models.User(
        username=signup.username,
        email=None,
        hashed_password=utils.get_password_hash(signup.password),
        register_ip=register_ip,
        is_verified=True,
        login_count=0,
        failed_attempts=0,
        total_online_seconds=0,
        created_at=now,
    )
    db.add(user)
    db.flush()

    identity = service.ensure_provider_identity(
        db,
        user=user,
        provider=WECHAT_MINI_PROVIDER,
        provider_subject=provider_subject,
        email=None,
        display_name=None,
        profile_picture=None,
        is_verified=True,
    )
    identity.identifier_normalized = payload.get("openid")
    db.commit()
    db.refresh(user)
    db.refresh(identity)
    return user, identity


def bind_wechat_mini_identity(
    db: Session,
    user: models.User,
    code: str,
    *,
    current_session_public_id: str | None,
) -> models.UserAuthIdentity:
    service.require_fresh_auth_session(db, user, current_session_public_id)
    payload = _load_wechat_mini_payload(code)
    provider_subject = payload.get("unionid") or payload["openid"]
    existing_identity = service.get_identity_by_provider_subject(db, WECHAT_MINI_PROVIDER, provider_subject)
    if existing_identity and existing_identity.user_id != user.id:
        raise service.AuthConflictError(
            "WeChat Mini account already linked to another account",
            conflict_code=service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED,
        )

    current_identity = db.query(models.UserAuthIdentity).filter(
        models.UserAuthIdentity.user_id == user.id,
        models.UserAuthIdentity.provider == WECHAT_MINI_PROVIDER,
    ).first()
    if current_identity and current_identity.provider_subject != provider_subject:
        raise service.AuthConflictError(
            "Current account already linked to another WeChat Mini account",
            conflict_code=service.CONFLICT_CODE_CURRENT_ACCOUNT_PROVIDER_MISMATCH,
            suggested_action=service.SUGGESTED_ACTION_REPLACE_EXISTING_PROVIDER_BINDING,
        )

    identity = service.ensure_provider_identity(
        db,
        user=user,
        provider=WECHAT_MINI_PROVIDER,
        provider_subject=provider_subject,
        email=None,
        display_name=None,
        profile_picture=None,
        is_verified=True,
    )
    identity.identifier_normalized = payload.get("openid")
    db.commit()
    db.refresh(identity)
    return identity


def rebind_wechat_mini_identity(
    db: Session,
    user: models.User,
    code: str,
    *,
    current_session_public_id: str | None,
) -> models.UserAuthIdentity:
    service.require_fresh_auth_session(db, user, current_session_public_id)
    payload = _load_wechat_mini_payload(code)
    provider_subject = payload.get("unionid") or payload["openid"]
    existing_identity = service.get_identity_by_provider_subject(db, WECHAT_MINI_PROVIDER, provider_subject)
    if existing_identity and existing_identity.user_id != user.id:
        raise service.AuthConflictError(
            "WeChat Mini account already linked to another account",
            conflict_code=service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED,
        )

    current_identity = db.query(models.UserAuthIdentity).filter(
        models.UserAuthIdentity.user_id == user.id,
        models.UserAuthIdentity.provider == WECHAT_MINI_PROVIDER,
    ).first()
    if current_identity:
        current_identity.provider_subject = provider_subject
        current_identity.identifier_normalized = payload.get("openid")
        current_identity.is_verified = True
        current_identity.last_login_at = utils.now_utc_naive()
        identity = current_identity
    else:
        identity = service.ensure_provider_identity(
            db,
            user=user,
            provider=WECHAT_MINI_PROVIDER,
            provider_subject=provider_subject,
            email=None,
            display_name=None,
            profile_picture=None,
            is_verified=True,
        )
        identity.identifier_normalized = payload.get("openid")

    db.commit()
    db.refresh(identity)
    return identity
