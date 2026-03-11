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


# /auth/me 專用響應體（不包含敏感安全信息）
class UserMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    role: str
    status: str
    is_verified: bool

    created_at: Optional[datetime] = None
    profile_picture: Optional[str] = None

    total_online_seconds: int

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


class RankingDetail(BaseModel):
    """Individual ranking detail"""
    rank: Optional[int] = Field(description="User's rank (null if no activity)")
    value: int = Field(description="User's value for this metric")
    gap_to_prev: Optional[int] = Field(description="Gap to previous rank (null for rank 1)")
    first_place_value: int = Field(description="First place user's value")


class LeaderboardResponse(BaseModel):
    """Complete leaderboard response with all 18 rankings"""
    rankings: dict[str, RankingDetail] = Field(
        description="Dictionary of all rankings (online_time, total_queries, categories, endpoints)"
    )
    total_users: int = Field(description="Total number of active users")


