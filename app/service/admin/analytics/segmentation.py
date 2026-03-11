"""
User Activity Segmentation Module

Segments users based on activity levels and recency.
"""

from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.service.auth.models import User, ApiUsageSummary


def get_user_segments(db: Session, include_users: bool = False) -> dict:
    """
    Segment users by activity level.

    Segmentation criteria:
    - Super Active: total_calls > 1000 AND active within 7 days
    - Active: total_calls > 500 AND active within 14 days
    - Regular: total_calls > 100 AND active within 30 days
    - Low Active: total_calls > 10 AND active within 60 days
    - Dormant: inactive for 60+ days

    Args:
        db: Database session
        include_users: Whether to include user details in response

    Returns:
        Dictionary with segment statistics
    """
    now = datetime.utcnow()

    # Get user statistics
    user_stats = db.query(
        User.id,
        User.username,
        User.last_seen,
        func.coalesce(func.sum(ApiUsageSummary.count), 0).label('total_calls'),
        func.coalesce(func.sum(ApiUsageSummary.total_duration), 0).label('total_duration')
    ).outerjoin(
        ApiUsageSummary, User.id == ApiUsageSummary.user_id
    ).group_by(User.id).all()

    # Initialize segments
    segments = {
        "super_active": {"users": [], "count": 0, "total_calls": 0, "total_duration": 0},
        "active": {"users": [], "count": 0, "total_calls": 0, "total_duration": 0},
        "regular": {"users": [], "count": 0, "total_calls": 0, "total_duration": 0},
        "low_active": {"users": [], "count": 0, "total_calls": 0, "total_duration": 0},
        "dormant": {"users": [], "count": 0, "total_calls": 0, "total_duration": 0},
    }

    # Classify users
    for user in user_stats:
        days_inactive = (now - user.last_seen).days if user.last_seen else 999
        total_calls = int(user.total_calls)
        total_duration = float(user.total_duration)

        user_data = {
            "user_id": user.id,
            "username": user.username,
            "total_calls": total_calls,
            "total_duration": round(total_duration, 2),
            "days_inactive": days_inactive,
            "last_seen": user.last_seen.isoformat() if user.last_seen else None
        }

        # Classify
        if total_calls > 1000 and days_inactive <= 7:
            segment = "super_active"
        elif total_calls > 500 and days_inactive <= 14:
            segment = "active"
        elif total_calls > 100 and days_inactive <= 30:
            segment = "regular"
        elif total_calls > 10 and days_inactive <= 60:
            segment = "low_active"
        else:
            segment = "dormant"

        segments[segment]["users"].append(user_data)
        segments[segment]["count"] += 1
        segments[segment]["total_calls"] += total_calls
        segments[segment]["total_duration"] += total_duration

    # Calculate statistics
    total_users = len(user_stats)
    result = {
        "segments": [],
        "total_users": total_users
    }

    for level, data in segments.items():
        segment_info = {
            "level": level,
            "count": data["count"],
            "percentage": round(data["count"] / total_users * 100, 2) if total_users > 0 else 0,
            "avg_calls": round(data["total_calls"] / data["count"], 2) if data["count"] > 0 else 0,
            "avg_duration": round(data["total_duration"] / data["count"], 2) if data["count"] > 0 else 0
        }

        if include_users:
            segment_info["users"] = data["users"]

        result["segments"].append(segment_info)

    return result
