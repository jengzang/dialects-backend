"""
Analytics Response Schemas

Pydantic models for analytics API responses.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# User Segmentation Schemas
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


# RFM Analysis Schemas
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


# Anomaly Detection Schemas
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


# API Diversity Schemas
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


# User Preferences Schemas
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


# User Growth Schemas
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


# Dashboard Schemas
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


# Trends Schemas
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


# Performance Schemas
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


# Geographic Distribution Schemas
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


# Device Distribution Schemas
class DeviceTypeItem(BaseModel):
    name: str
    count: int
    percentage: float


class DeviceDistributionResponse(BaseModel):
    device_types: List[DeviceTypeItem]
    browsers: List[DeviceTypeItem]
    os: List[DeviceTypeItem]
    total_users: int
