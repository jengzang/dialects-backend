# schemas/admin/analytics.py
"""
管理后台 - 分析统计相关 schemas

包含：
- Leaderboard: 排行榜
- User Segmentation: 用户分段
- RFM Analysis: RFM分析
- Anomaly Detection: 异常检测
- API Diversity: API多样性
- User Preferences: 用户偏好
- User Growth: 用户增长
- Dashboard: 仪表板
- Trends: 趋势分析
- Performance: 性能分析
- Geographic Distribution: 地理分布
- Device Distribution: 设备分布
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ===== Leaderboard Schemas =====

class LeaderboardQueryParams(BaseModel):
    """排行榜查询参数"""
    ranking_type: str  # "user_global", "user_by_api", "api", "online_time"
    metric: Optional[str] = None  # "count", "duration", "upload", "download"
    api_path: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class UserRankingItem(BaseModel):
    """用户排名项"""
    rank: int
    user_id: int
    username: str
    value: float
    percentage: float
    gap_to_prev: Optional[float] = None
    first_place_value: float


class ApiRankingItem(BaseModel):
    """API排名项"""
    rank: int
    path: str
    value: float
    percentage: float
    unique_users: int
    gap_to_prev: Optional[float] = None
    first_place_value: float


class LeaderboardResponse(BaseModel):
    """排行榜响应"""
    ranking_type: str
    metric: Optional[str]
    api_path: Optional[str]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    rankings: list
    total_value: Optional[float] = Field(None, description="所有排名项目的累计总量（不受分页限制）")


class AvailableApisResponse(BaseModel):
    """可用API列表响应"""
    apis: list[str]


# ===== User Segmentation Schemas =====
class UserSegmentItem(BaseModel):
    user_id: int
    username: str
    total_calls: int
    total_duration: float
    days_inactive: int
    last_seen: Optional[str]


class SegmentInfo(BaseModel):
    level: str
    count: int
    percentage: float
    avg_calls: float
    avg_duration: float
    users: Optional[List[UserSegmentItem]] = None


class UserSegmentsResponse(BaseModel):
    segments: List[SegmentInfo]
    total_users: int


# ===== RFM Analysis Schemas =====
class RFMUserItem(BaseModel):
    user_id: int
    username: str
    recency_days: int
    frequency: int
    monetary: float
    last_seen: Optional[str]
    r_score: int
    f_score: int
    m_score: int
    segment: str


class RFMSegmentInfo(BaseModel):
    segment: str
    count: int
    avg_recency_days: float
    avg_frequency: float
    avg_monetary: float
    users: Optional[List[RFMUserItem]] = None


class RFMAnalysisResponse(BaseModel):
    segments: List[RFMSegmentInfo]


# ===== Anomaly Detection Schemas =====
class AnomalyItem(BaseModel):
    type: str
    user_id: int
    username: str
    value: float
    severity: str
    avg_value: Optional[float] = None
    z_score: Optional[float] = None
    top_api: Optional[str] = None
    api_calls: Optional[int] = None
    total_calls: Optional[int] = None
    days_since_registration: Optional[int] = None
    calls_per_day: Optional[float] = None


class AnomalyDetectionResponse(BaseModel):
    anomalies: List[AnomalyItem]


# ===== API Diversity Schemas =====
class DiversityUserItem(BaseModel):
    user_id: int
    username: str
    api_count: int
    total_calls: int
    diversity_score: float
    user_type: str


class DiversitySummary(BaseModel):
    total_users: int
    avg_diversity: float
    explorer_count: int
    focused_count: int


class APIDiversityResponse(BaseModel):
    users: List[DiversityUserItem]
    summary: DiversitySummary


# ===== User Preferences Schemas =====
class TopAPIItem(BaseModel):
    path: str
    calls: int
    percentage: float


class TrafficPattern(BaseModel):
    upload_ratio: float
    download_ratio: float
    total_traffic_kb: float


class UserPreferenceItem(BaseModel):
    user_id: int
    username: str
    category_distribution: Dict[str, float]
    total_calls: int
    api_diversity: int
    diversity_score: float
    traffic_pattern: TrafficPattern
    top_apis: List[TopAPIItem]


class UserPreferencesResponse(BaseModel):
    users: List[UserPreferenceItem]


# ===== User Growth Schemas =====
class MonthlyGrowthItem(BaseModel):
    month: str
    new_users: int
    cumulative_users: int
    growth_rate: float


class GrowthSummary(BaseModel):
    total_users: int
    avg_monthly_growth: float
    months_analyzed: int


class UserGrowthResponse(BaseModel):
    monthly_growth: List[MonthlyGrowthItem]
    summary: GrowthSummary


# ===== Dashboard Schemas =====
class DashboardOverview(BaseModel):
    total_users: int
    active_users_7d: int
    active_users_30d: int
    total_calls: int
    total_traffic_mb: float


class TopAPIItem(BaseModel):
    path: str
    calls: int
    users: int


class MonthlyNewUsersItem(BaseModel):
    month: str
    new_users: int


class DashboardResponse(BaseModel):
    overview: DashboardOverview
    top_apis: List[TopAPIItem]
    user_distribution: Dict[str, int]
    monthly_new_users: List[MonthlyNewUsersItem]


# ===== Trends Schemas =====
class TrendItem(BaseModel):
    time: str
    total_calls: int
    active_users: int
    avg_duration: float
    top_api: Optional[str]


class TrendsSummary(BaseModel):
    total_calls: int
    avg_daily_calls: float
    peak_time: Optional[str]
    peak_calls: int


class RecentTrendsResponse(BaseModel):
    period: str
    granularity: str
    trends: List[TrendItem]
    summary: TrendsSummary


# ===== Performance Schemas =====
class APIPerformanceItem(BaseModel):
    path: str
    avg_duration: float
    p50: float
    p95: float
    p99: float
    slow_request_ratio: float
    total_calls: int


class PerformanceSummary(BaseModel):
    overall_avg: float
    slowest_api: Optional[str]
    total_apis: int


class APIPerformanceResponse(BaseModel):
    apis: List[APIPerformanceItem]
    summary: PerformanceSummary


# ===== Geographic Distribution Schemas =====
class GeoDistributionItem(BaseModel):
    location: str
    user_count: int
    call_count: int
    percentage: float


class GeoDistributionResponse(BaseModel):
    level: str
    distribution: List[GeoDistributionItem]
    total_locations: int
    error: Optional[str] = None


# ===== Device Distribution Schemas =====
class DeviceTypeItem(BaseModel):
    name: str
    count: int
    percentage: float


class DeviceDistributionResponse(BaseModel):
    device_types: List[DeviceTypeItem]
    browsers: List[DeviceTypeItem]
    os: List[DeviceTypeItem]
    total_users: int
