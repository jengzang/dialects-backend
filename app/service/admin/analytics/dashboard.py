"""
System Overview Dashboard Module

Provides comprehensive system statistics.
"""

from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.service.auth.models import User, ApiUsageSummary
from .segmentation import get_user_segments
from .growth import get_user_growth


def get_dashboard_data(db: Session) -> dict:
    """
    Get comprehensive dashboard statistics.

    Args:
        db: Database session

    Returns:
        Dictionary with dashboard data
    """
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Total users
    total_users = db.query(func.count(User.id)).scalar()

    # Active users (7 days and 30 days)
    active_users_7d = db.query(func.count(User.id)).filter(
        User.last_seen >= seven_days_ago
    ).scalar()

    active_users_30d = db.query(func.count(User.id)).filter(
        User.last_seen >= thirty_days_ago
    ).scalar()

    # Total calls and traffic
    usage_stats = db.query(
        func.sum(ApiUsageSummary.count).label('total_calls'),
        func.sum(ApiUsageSummary.total_upload + ApiUsageSummary.total_download).label('total_traffic')
    ).first()

    total_calls = int(usage_stats.total_calls) if usage_stats.total_calls else 0
    total_traffic_kb = float(usage_stats.total_traffic) if usage_stats.total_traffic else 0
    total_traffic_mb = round(total_traffic_kb / 1024, 2)

    # Top APIs
    top_apis_data = db.query(
        ApiUsageSummary.path,
        func.sum(ApiUsageSummary.count).label('total_calls'),
        func.count(func.distinct(ApiUsageSummary.user_id)).label('user_count')
    ).group_by(
        ApiUsageSummary.path
    ).order_by(
        func.sum(ApiUsageSummary.count).desc()
    ).limit(10).all()

    top_apis = [
        {
            "path": api.path,
            "calls": int(api.total_calls),
            "users": int(api.user_count)
        }
        for api in top_apis_data
    ]

    # User distribution (from segmentation)
    segments_data = get_user_segments(db, include_users=False)
    user_distribution = {}
    for segment in segments_data["segments"]:
        user_distribution[segment["level"]] = segment["count"]

    # Monthly new users (last 6 months)
    growth_data = get_user_growth(db, months=6)
    monthly_new_users = [
        {
            "month": m["month"],
            "new_users": m["new_users"]
        }
        for m in growth_data["monthly_growth"]
    ]

    return {
        "overview": {
            "total_users": total_users,
            "active_users_7d": active_users_7d,
            "active_users_30d": active_users_30d,
            "total_calls": total_calls,
            "total_traffic_mb": total_traffic_mb
        },
        "top_apis": top_apis,
        "user_distribution": user_distribution,
        "monthly_new_users": monthly_new_users
    }
