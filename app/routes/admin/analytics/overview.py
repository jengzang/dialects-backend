"""
Analytics API Routes

Admin-only endpoints for user behavior analytics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.service.auth.core.dependencies import get_current_admin_user
from app.service.auth.database.models import User
from app.service.auth.database.connection import get_db
from app.schemas.admin.analytics import (
    UserSegmentsResponse,
    RFMAnalysisResponse,
    AnomalyDetectionResponse,
    APIDiversityResponse,
    UserPreferencesResponse,
    UserGrowthResponse,
    DashboardResponse,
    RecentTrendsResponse,
    APIPerformanceResponse,
    GeoDistributionResponse,
    DeviceDistributionResponse,
)
from app.service.admin.analytics import (
    get_user_segments,
    get_rfm_analysis,
    detect_anomalies,
    get_api_diversity,
    get_user_preferences,
    get_user_growth,
    get_dashboard_data,
    get_recent_trends,
    get_api_performance,
    get_geo_distribution,
    get_device_distribution,
    export_data,
)

router = APIRouter()


@router.get("/user-segments", response_model=UserSegmentsResponse)
async def api_user_segments(
    include_users: bool = Query(False, description="Include user details"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get user activity segmentation.

    Segments users into: super_active, active, regular, low_active, dormant
    """
    return get_user_segments(db, include_users=include_users)


@router.get("/rfm-analysis", response_model=RFMAnalysisResponse)
async def api_rfm_analysis(
    include_users: bool = Query(False, description="Include user details"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Perform RFM (Recency, Frequency, Monetary) user value analysis.

    Segments users into: VIP, Potential, New, Dormant High Value, Low Value, Others
    """
    return get_rfm_analysis(db, include_users=include_users)


@router.get("/anomaly-detection", response_model=AnomalyDetectionResponse)
async def api_anomaly_detection(
    detection_type: str = Query("all", description="Type: all, high_frequency, high_traffic, single_api, new_user_spike"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Detect anomalous user behavior patterns.

    Detection types:
    - high_frequency: Users with calls > mean + 3*std
    - high_traffic: Users with traffic > mean + 3*std
    - single_api: Users with 90%+ calls on single API
    - new_user_spike: Users registered < 7 days with > 100 calls
    - all: All detection types
    """
    return detect_anomalies(db, detection_type=detection_type)


@router.get("/api-diversity", response_model=APIDiversityResponse)
async def api_diversity_analysis(
    sort_by: str = Query("diversity", description="Sort by: diversity or calls"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Analyze API usage diversity for each user.

    Returns diversity scores and classifies users as explorers or focused users.
    """
    return get_api_diversity(db, sort_by=sort_by)


@router.get("/user-preferences", response_model=UserPreferencesResponse)
async def api_user_preferences(
    user_ids: Optional[str] = Query(None, description="Comma-separated user IDs"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Analyze user preferences based on API usage patterns.

    Returns detailed data for frontend to generate labels.
    """
    user_id_list = None
    if user_ids:
        user_id_list = [int(uid.strip()) for uid in user_ids.split(",")]

    return get_user_preferences(db, user_ids=user_id_list)


@router.get("/user-growth", response_model=UserGrowthResponse)
async def api_user_growth(
    months: int = Query(12, description="Number of recent months to analyze"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Analyze user growth statistics by month.

    Returns monthly new users, cumulative users, and growth rates.
    """
    return get_user_growth(db, months=months)


@router.get("/dashboard", response_model=DashboardResponse)
async def api_dashboard(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive system overview dashboard.

    Includes:
    - Total users, active users (7d/30d)
    - Total calls and traffic
    - Top APIs
    - User distribution by activity level
    - Monthly new users trend
    """
    return get_dashboard_data(db)


@router.get("/recent-trends", response_model=RecentTrendsResponse)
async def api_recent_trends(
    granularity: str = Query("day", description="Granularity: day or hour"),
    days: int = Query(7, description="Number of days to analyze (max 7)"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Analyze recent API usage trends (last 7 days).

    Returns daily/hourly call counts, active users, and performance metrics.
    """
    return get_recent_trends(db, granularity=granularity, days=days)


@router.get("/api-performance", response_model=APIPerformanceResponse)
async def api_performance_analysis(
    api_path: Optional[str] = Query(None, description="Specific API path to analyze"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Analyze API performance metrics.

    Returns average response time, percentiles (P50/P95/P99), and slow request ratios.
    """
    return get_api_performance(db, api_path=api_path)


@router.get("/geo-distribution", response_model=GeoDistributionResponse)
async def api_geo_distribution(
    level: str = Query("country", description="Level: country or city"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Analyze geographic distribution of users.

    Uses GeoLite2 database to resolve IP addresses to locations.
    """
    return get_geo_distribution(db, level=level)


@router.get("/device-distribution", response_model=DeviceDistributionResponse)
async def api_device_distribution(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Analyze user device distribution.

    Returns device types (desktop/mobile/tablet), browsers, and operating systems.
    """
    return get_device_distribution(db)


@router.get("/export")
async def api_export_data(
    export_type: str = Query(..., description="Type: user-segments, rfm, anomalies, diversity, preferences, growth, dashboard, trends, performance, geo, devices"),
    format: str = Query("csv", description="Format: csv, xlsx, json"),
    flatten: bool = Query(False, description="Flatten nested structures for CSV/Excel"),
    include_users: bool = Query(False, description="Include user details (where applicable)"),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Export analytics data in various formats.

    Supported formats: CSV, Excel (XLSX), JSON
    """
    # Get data based on export type
    if export_type == "user-segments":
        data = get_user_segments(db, include_users=include_users)
        filename = "user_segments"
    elif export_type == "rfm":
        data = get_rfm_analysis(db, include_users=include_users)
        filename = "rfm_analysis"
    elif export_type == "anomalies":
        data = detect_anomalies(db)
        filename = "anomaly_detection"
    elif export_type == "diversity":
        data = get_api_diversity(db)
        filename = "api_diversity"
    elif export_type == "preferences":
        data = get_user_preferences(db)
        filename = "user_preferences"
    elif export_type == "growth":
        data = get_user_growth(db)
        filename = "user_growth"
    elif export_type == "dashboard":
        data = get_dashboard_data(db)
        filename = "dashboard"
    elif export_type == "trends":
        data = get_recent_trends(db)
        filename = "recent_trends"
    elif export_type == "performance":
        data = get_api_performance(db)
        filename = "api_performance"
    elif export_type == "geo":
        data = get_geo_distribution(db)
        filename = "geo_distribution"
    elif export_type == "devices":
        data = get_device_distribution(db)
        filename = "device_distribution"
    else:
        return {"error": f"Unknown export type: {export_type}"}

    # Export data
    return export_data(data, format, filename, flatten=flatten)
