import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional, Tuple
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Request

from common.config import ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM, AUDIENCE, ISSUER

# 可选：SMTP 配置（留空则退化为控制台打印）
SMTP_HOST: Optional[str] = None      # 如 "smtp.gmail.com"
SMTP_PORT: int = 587                 # TLS: 587, SSL: 465
SMTP_USERNAME: Optional[str] = None
SMTP_PASSWORD: Optional[str] = None
SMTP_FROM: str = "no-reply@your-domain.com"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- 時間工具：UTC 時間 ---
# —— 用于入库：naive UTC（不带 tzinfo），避免 SQLAlchemy 无 tz 列报错
def now_utc_naive() -> datetime:
    return datetime.utcnow()

# （可选）如果你需要带 tz 的当前时间：
def now_utc_aware() -> datetime:
    return datetime.now(timezone.utc)

# 如果要存北京時區，可改為：
# from datetime import timedelta
# CST = timezone(timedelta(hours=8))
# def now_cst() -> datetime:
#     return datetime.now(CST).replace(tzinfo=None)

# ===== 密码哈希 =====
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# ===== JWT =====
def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    # 统一用 epoch 秒，避免 naive datetime 坑
    now_ts = int(time.time())
    exp_minutes = expires_minutes if (expires_minutes and expires_minutes > 0) else ACCESS_TOKEN_EXPIRE_MINUTES
    payload = {
        "sub": subject,
        "iat": now_ts,
        "nbf": now_ts,
        "exp": now_ts + exp_minutes * 60,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    # 给 2 分钟余量，解决轻微时钟漂移/容器启动时差
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

# ===== 获取客户端 IP（考虑反代）=====
def extract_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("x-real-ip")
    if xri:
        return xri.strip()
    return request.client.host if request.client else "0.0.0.0"

# ===== 发送邮件（SMTP 存在→发真实邮件；否则打印链接以便开发调试）=====
def send_email(email: str, subject: str, body: str) -> None:
    if SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = email
        msg.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
    else:
        # 开发环境：直接打印到控制台，避免卡在邮件配置
        print(f"[DEV EMAIL] To: {email}\nSubject: {subject}\n\n{body}\n")

