from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import check_login_rate_limit
from app.auth.models import ApiUsageLog
from app.auth.service import update_user_profile
from app.schemas import auth as schemas
from app.auth import service, utils, models
from app.auth.database import get_db
from common.config import REQUIRE_EMAIL_VERIFICATION

router = APIRouter()
# Swagger 的 "Authorize" 按钮会用到这个 tokenUrl
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


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
    agent = request.headers.get("user-agent", "")
    try:
        user = service.authenticate_user(db, form_data.username, form_data.password, login_ip=client_ip)
    except PermissionError:
        # [X] 驗證失敗也記 log
        db.add(ApiUsageLog(
            user_id=None,
            path="/login",
            duration=0,
            status_code=403,
            ip=client_ip,
            called_at=datetime.utcnow(),
            user_agent=agent
        ))
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")
    except ValueError:
        db.add(ApiUsageLog(
            user_id=None,
            path="/login",
            duration=0,
            status_code=401,
            ip=client_ip,
            called_at=datetime.utcnow(),
            user_agent=agent
        ))
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # [OK] 成功登入後也寫入一筆記錄
    db.add(ApiUsageLog(
        user_id=user.id,
        path="/login",
        duration=0,
        status_code=200,
        ip=client_ip,
        called_at=datetime.utcnow()
    ))
    db.commit()

    # Create token pair
    token_pair = utils.create_token_pair(user.username)

    # Store refresh token in database
    device_info = request.headers.get("User-Agent") if request else None
    service.store_refresh_token(
        db,
        user.id,
        token_pair["refresh_token"],
        device_info
    )

    return token_pair


# Token refresh endpoint
@router.post("/refresh", response_model=schemas.TokenPair)
def refresh(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    Exchange refresh token for new access + refresh token pair.
    Implements token rotation for security.
    """
    # Validate refresh token
    token_obj = service.validate_refresh_token(db, refresh_token)
    if not token_obj:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )

    # Get user
    user = db.query(models.User).filter(
        models.User.id == token_obj.user_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create new token pair
    new_token_pair = utils.create_token_pair(user.username)

    # Rotate refresh token (revoke old, store new)
    new_refresh_token_str, _ = service.rotate_refresh_token(db, token_obj)
    new_token_pair["refresh_token"] = new_refresh_token_str

    return new_token_pair


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
@router.get("/me", response_model=schemas.UserResponse)
def me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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
    # service.touch_activity(user)  # 队列版本不需要 db 参数
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
    try:
        payload = utils.decode_access_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token (no subject)")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Accumulate online time
    session_seconds, total_seconds = service.logout_user(db, user)

    # Revoke tokens
    if logout_all:
        service.revoke_all_user_tokens(db, user.id)
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
    seconds: int = Body(..., embed=True, ge=1, le=3600),  # 1秒到1小时
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    前端上报在线时长

    前端应该：
    1. 使用 Page Visibility API 监听页面可见性
    2. 当页面可见时开始计时
    3. 当页面不可见或定期（如每分钟）上报累计时长

    参数：
    - seconds: 本次上报的在线时长（秒），范围 1-3600

    返回：
    - success: 是否成功
    - total_online_seconds: 用户总在线时长（秒）
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

    # 调用队列版本的函数（异步处理）
    service.accumulate_online_time(user, seconds)

    # 返回当前的总在线时长（注意：由于队列异步处理，这个值可能有延迟）
    return {
        "success": True,
        "reported_seconds": seconds,
        "total_online_seconds": user.total_online_seconds or 0,
        "message": "在线时长已记录（异步处理中）"
    }


@router.put("/updateProfile")
async def update_profile(
    username: str = Form(None),  # 使用 Form 获取数据
    email: str = Form(...),
    password: str = Form(None),
    new_password: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):

    try:
        updated_user = update_user_profile(
            db=db,
            email=email,
            username=username,
            password=password,
            new_password=new_password
        )
        return {"message": "用戶資料更新成功！", "user": {"username": updated_user.username, "email": updated_user.email}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
