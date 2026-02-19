"""Session 管理相关的 Pydantic 模型"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class IPHistoryItem(BaseModel):
    """IP 历史记录项"""
    ip: str
    timestamp: str

    @field_validator('timestamp')
    @classmethod
    def parse_timestamp(cls, v):
        """确保 timestamp 是 ISO 格式"""
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class SessionDetailResponse(BaseModel):
    """完整会话详情"""
    # 身份信息
    id: int
    session_id: str
    user_id: int
    username: str

    # 生命周期
    created_at: datetime
    expires_at: datetime
    last_activity_at: datetime
    revoked: bool
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None

    # 设备跟踪
    device_info: Optional[str] = None
    first_device_info: Optional[str] = None
    device_fingerprint: Optional[str] = None
    device_change_count: int
    device_changed: bool

    # 网络跟踪
    current_ip: str
    first_ip: str
    ip_change_count: int
    ip_history: List[IPHistoryItem] = Field(default_factory=list)

    # 统计信息
    refresh_count: int
    total_online_seconds: int
    current_session_started_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    # 安全标记
    is_suspicious: bool
    suspicious_reason: Optional[str] = None

    # 计算字段
    active_token_count: int = 0

    class Config:
        from_attributes = True


class SessionSummaryResponse(BaseModel):
    """会话摘要（用于列表视图）"""
    id: int
    session_id: str
    user_id: int
    username: str
    created_at: datetime
    expires_at: datetime
    last_activity_at: datetime
    revoked: bool
    current_ip: str
    device_info: Optional[str] = None
    is_suspicious: bool
    refresh_count: int
    active_token_count: int = 0

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """分页会话列表"""
    total: int
    skip: int
    limit: int
    sessions: List[SessionSummaryResponse]


class SessionStatsResponse(BaseModel):
    """会话统计汇总"""
    total_sessions: int
    active_sessions: int
    revoked_sessions: int
    expired_sessions: int
    suspicious_sessions: int
    unique_users_with_sessions: int
    total_online_hours: float
    avg_session_duration_hours: float
    top_ip_changes: List[Dict[str, Any]] = Field(default_factory=list)
    top_device_changes: List[Dict[str, Any]] = Field(default_factory=list)


class SessionActivityItem(BaseModel):
    """会话活动时间线项"""
    timestamp: datetime
    event_type: str = Field(
        description="Event type: created, refreshed, ip_changed, device_changed, flagged_suspicious, revoked"
    )
    details: str


class SessionActivityResponse(BaseModel):
    """会话活动时间线"""
    session_id: str
    user_id: int
    username: str
    events: List[SessionActivityItem]


class RevokeSessionRequest(BaseModel):
    """批量撤销请求"""
    session_ids: List[int] = Field(min_length=1, max_length=100)
    reason: str = Field(default="admin_action", max_length=100)


class RevokeSessionResponse(BaseModel):
    """撤销会话响应"""
    message: str
    revoked_tokens: int


class RevokeBulkResponse(BaseModel):
    """批量撤销响应"""
    revoked_count: int
    failed_count: int = 0
    details: List[Dict[str, Any]] = Field(default_factory=list)


class FlagSessionRequest(BaseModel):
    """标记会话请求"""
    is_suspicious: bool
    reason: Optional[str] = Field(None, max_length=255)
