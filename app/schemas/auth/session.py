"""Session-related Pydantic schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, Field, field_validator

from app.common.time_utils import to_shanghai_iso
from app.schemas.base import ShanghaiBaseModel


class IPHistoryItem(ShanghaiBaseModel):
    ip: str
    location: Optional[str] = None
    timestamp: str

    @field_validator("timestamp")
    @classmethod
    def parse_timestamp(cls, value: str | datetime):
        if isinstance(value, datetime):
            return to_shanghai_iso(value)
        return to_shanghai_iso(value) or value


class SessionDetailResponse(ShanghaiBaseModel):
    id: int
    session_id: str
    user_id: int
    username: str

    created_at: datetime
    expires_at: datetime
    last_activity_at: datetime
    revoked: bool
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None

    device_info: Optional[str] = None
    first_device_info: Optional[str] = None
    device_fingerprint: Optional[str] = None
    device_change_count: int
    device_changed: bool

    current_ip: str
    current_ip_location: Optional[str] = None
    first_ip: str
    first_ip_location: Optional[str] = None
    ip_change_count: int
    ip_history: List[IPHistoryItem] = Field(default_factory=list)

    refresh_count: int
    total_online_seconds: int
    current_session_started_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    is_suspicious: bool
    suspicious_reason: Optional[str] = None
    active_token_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SessionSummaryResponse(ShanghaiBaseModel):
    id: int
    session_id: str
    user_id: int
    username: str
    created_at: datetime
    expires_at: datetime
    last_activity_at: datetime
    revoked: bool
    current_ip: str
    current_ip_location: Optional[str] = None
    device_info: Optional[str] = None
    is_suspicious: bool
    refresh_count: int
    active_token_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SessionListResponse(ShanghaiBaseModel):
    total: int
    skip: int
    limit: int
    sessions: List[SessionSummaryResponse]


class SessionStatsResponse(ShanghaiBaseModel):
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


class SessionActivityItem(ShanghaiBaseModel):
    timestamp: datetime
    event_type: str = Field(
        description="Event type: created, refreshed, ip_changed, device_changed, flagged_suspicious, revoked"
    )
    details: str


class SessionActivityResponse(ShanghaiBaseModel):
    session_id: str
    user_id: int
    username: str
    events: List[SessionActivityItem]


class RevokeSessionRequest(ShanghaiBaseModel):
    session_ids: List[int] = Field(min_length=1, max_length=100)
    reason: str = Field(default="admin_action", max_length=100)


class RevokeSessionResponse(ShanghaiBaseModel):
    message: str
    revoked_tokens: int


class RevokeBulkResponse(ShanghaiBaseModel):
    revoked_count: int
    failed_count: int = 0
    details: List[Dict[str, Any]] = Field(default_factory=list)


class FlagSessionRequest(ShanghaiBaseModel):
    is_suspicious: bool
    reason: Optional[str] = Field(None, max_length=255)


class DailyActivityItem(ShanghaiBaseModel):
    date: str
    count: int


class UserActivityData(ShanghaiBaseModel):
    dau: List[DailyActivityItem] = Field(description="Daily active users for recent days")
    wau: int = Field(description="Weekly active users")
    mau: int = Field(description="Monthly active users")


class DeviceDistribution(ShanghaiBaseModel):
    desktop: int
    mobile: int
    tablet: int
    unknown: int


class GeoDistributionItem(ShanghaiBaseModel):
    country: str
    count: int


class SessionDurationDistribution(ShanghaiBaseModel):
    duration_0_5min: int = Field(alias="0-5min")
    duration_5_30min: int = Field(alias="5-30min")
    duration_30_60min: int = Field(alias="30-60min")
    duration_1_2h: int = Field(alias="1-2h")
    duration_2h_plus: int = Field(alias="2h+")

    model_config = ConfigDict(populate_by_name=True)


class AnalyticsResponse(ShanghaiBaseModel):
    login_heatmap: List[List[int]] = Field(description="7x24 login heatmap")
    user_activity: UserActivityData
    device_distribution: DeviceDistribution
    geo_distribution: List[GeoDistributionItem]
    session_duration_distribution: SessionDurationDistribution


class OnlineUserItem(ShanghaiBaseModel):
    user_id: int
    username: str
    last_seen: datetime
    current_ip: str
    current_ip_location: Optional[str] = None
    device_info: Optional[str] = None


class OnlineUsersResponse(ShanghaiBaseModel):
    online_count: int
    users: List[OnlineUserItem]

