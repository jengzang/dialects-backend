from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


# 請求體
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    # full_name: Optional[str] = None
    # phone: Optional[str] = None


class ApiUsageStat(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    path: str
    count: int

# 響應體
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # ← 代替 v1 的 orm_mode=True

    id: int
    username: str
    email: EmailStr
    # full_name: Optional[str] = None
    # phone: Optional[str] = None
    role: str
    status: str
    is_verified: bool

    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    register_ip: Optional[str] = None

    login_count: int
    failed_attempts: int
    last_failed_login: Optional[datetime] = None

    total_online_seconds: int
    current_session_started_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    usage_summary: List[ApiUsageStat] = []


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until access token expires


class LogoutResponse(BaseModel):
    message: str
    session_seconds: int
    total_online_seconds: int


