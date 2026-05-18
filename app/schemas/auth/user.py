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
    email: Optional[EmailStr] = None
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


# /api/auth/me 專用響應體（不包含敏感安全信息）
class AuthProviderStatus(BaseModel):
    provider: str
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    is_verified: bool
    is_primary: bool
    linked_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    profile_picture: Optional[str] = None
    can_unbind: bool = False
    can_replace: bool = False
    replacement_action: Optional[str] = None


class AuthProviderMutationResponse(BaseModel):
    message: str
    providers: List[AuthProviderStatus] = []


class UserMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[EmailStr] = None
    role: str
    status: str
    is_verified: bool

    created_at: Optional[datetime] = None
    profile_picture: Optional[str] = None

    total_online_seconds: int

    usage_summary: List[ApiUsageStat] = []
    auth_providers: List[AuthProviderStatus] = []


class EmailRequest(BaseModel):
    email: EmailStr


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    current_password: str = Field(min_length=6, max_length=128)


class ChangeEmailResponse(BaseModel):
    message: str
    email: EmailStr
    is_verified: bool
    providers: List[AuthProviderStatus] = []


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)
    revoke_other_sessions: bool = False


class ChangePasswordResponse(BaseModel):
    message: str
    revoked_other_sessions: bool


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)


class EmailRegistrationStartRequest(BaseModel):
    email: EmailStr


class EmailRegistrationCompleteRequest(BaseModel):
    token: str
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class EmailRegistrationVerifyResponse(BaseModel):
    email: EmailStr
    ready_to_complete: bool


class OAuthStartRequest(BaseModel):
    intent: str = Field(default="login_or_register")
    redirect_uri: Optional[str] = None
    current_session_id: Optional[str] = None


class OAuthStartResponse(BaseModel):

    authorize_url: str
    state: str
    expires_in: int
    intent: str


class OAuthCallbackRequest(BaseModel):
    state: str = Field(min_length=8)
    id_token: Optional[str] = None
    access_token: Optional[str] = None
    openid: Optional[str] = None


class GoogleTokenRequest(BaseModel):
    id_token: str = Field(min_length=20)


class GoogleRegisterRequest(BaseModel):
    id_token: str = Field(min_length=20)
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class WechatTokenRequest(BaseModel):
    access_token: str = Field(min_length=1)
    openid: str = Field(min_length=1)


class WechatRegisterRequest(BaseModel):
    access_token: str = Field(min_length=1)
    openid: str = Field(min_length=1)
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class AuthConflictResponse(BaseModel):
    message: str
    conflict_code: str
    suggested_action: Optional[str] = None


class GoogleAuthResponse(BaseModel):
    action: str
    message: str
    username: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = "bearer"
    expires_in: Optional[int] = None
    email: Optional[EmailStr] = None
    suggested_username: Optional[str] = None
    conflict_code: Optional[str] = None
    suggested_action: Optional[str] = None
    is_verified: Optional[bool] = None
    profile_picture: Optional[str] = None


class WechatAuthResponse(BaseModel):
    action: str
    message: str
    username: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = "bearer"
    expires_in: Optional[int] = None
    suggested_username: Optional[str] = None
    conflict_code: Optional[str] = None
    suggested_action: Optional[str] = None
    profile_picture: Optional[str] = None
    provider_subject: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


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
    """Complete leaderboard response with category, grouped, and endpoint rankings."""
    rankings: dict[str, RankingDetail] = Field(
        description="Dictionary of all rankings (online_time, total_queries, categories, grouped aggregates, endpoints)"
    )
    total_users: int = Field(description="Total number of active users")
