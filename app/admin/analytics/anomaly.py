"""
Anomaly Detection Module

Detects anomalous user behavior patterns.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
import statistics

from app.auth.models import User, ApiUsageSummary


def detect_anomalies(
    db: Session,
    detection_type: str = "all"
) -> dict:
    """
    Detect anomalous user behavior.

    Detection types:
    - high_frequency: Users with calls > mean + 3*std
    - high_traffic: Users with traffic > mean + 3*std
    - single_api: Users with 90%+ calls on single API
    - new_user_spike: Users registered < 7 days with > 100 calls
    - all: All detection types

    Args:
        db: Database session
        detection_type: Type of anomaly to detect

    Returns:
        Dictionary with detected anomalies
    """
    anomalies = []

    # Get user statistics
    user_stats = db.query(
        User.id,
        User.username,
        User.created_at,
        func.coalesce(func.sum(ApiUsageSummary.count), 0).label('total_calls'),
        func.coalesce(func.sum(ApiUsageSummary.total_upload + ApiUsageSummary.total_download), 0).label('total_traffic')
    ).outerjoin(
        ApiUsageSummary, User.id == ApiUsageSummary.user_id
    ).group_by(User.id).all()

    if not user_stats:
        return {"anomalies": []}

    # High frequency detection
    if detection_type in ["all", "high_frequency"]:
        call_counts = [int(u.total_calls) for u in user_stats if u.total_calls > 0]
        if call_counts:
            mean_calls = statistics.mean(call_counts)
            std_calls = statistics.stdev(call_counts) if len(call_counts) > 1 else 0
            threshold = mean_calls + 3 * std_calls

            for user in user_stats:
                calls = int(user.total_calls)
                if calls > threshold:
                    z_score = (calls - mean_calls) / std_calls if std_calls > 0 else 0
                    anomalies.append({
                        "type": "high_frequency",
                        "user_id": user.id,
                        "username": user.username,
                        "value": calls,
                        "avg_value": round(mean_calls, 2),
                        "z_score": round(z_score, 2),
                        "severity": "high" if z_score > 5 else "medium"
                    })

    # High traffic detection
    if detection_type in ["all", "high_traffic"]:
        traffic_values = [float(u.total_traffic) for u in user_stats if u.total_traffic > 0]
        if traffic_values:
            mean_traffic = statistics.mean(traffic_values)
            std_traffic = statistics.stdev(traffic_values) if len(traffic_values) > 1 else 0
            threshold = mean_traffic + 3 * std_traffic

            for user in user_stats:
                traffic = float(user.total_traffic)
                if traffic > threshold:
                    z_score = (traffic - mean_traffic) / std_traffic if std_traffic > 0 else 0
                    anomalies.append({
                        "type": "high_traffic",
                        "user_id": user.id,
                        "username": user.username,
                        "value": round(traffic, 2),
                        "avg_value": round(mean_traffic, 2),
                        "z_score": round(z_score, 2),
                        "severity": "high" if z_score > 5 else "medium"
                    })

    # Single API dependency detection
    if detection_type in ["all", "single_api"]:
        for user in user_stats:
            if user.total_calls > 0:
                # Get API distribution for this user
                api_usage = db.query(
                    ApiUsageSummary.path,
                    ApiUsageSummary.count
                ).filter(
                    ApiUsageSummary.user_id == user.id
                ).all()

                if api_usage:
                    max_api_calls = max(int(u.count) for u in api_usage)
                    total_calls = int(user.total_calls)
                    concentration = (max_api_calls / total_calls * 100) if total_calls > 0 else 0

                    if concentration >= 90:
                        top_api = max(api_usage, key=lambda x: x.count)
                        anomalies.append({
                            "type": "single_api",
                            "user_id": user.id,
                            "username": user.username,
                            "value": round(concentration, 2),
                            "top_api": top_api.path,
                            "api_calls": int(top_api.count),
                            "total_calls": total_calls,
                            "severity": "medium"
                        })

    # New user spike detection
    if detection_type in ["all", "new_user_spike"]:
        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)

        for user in user_stats:
            if user.created_at and user.created_at >= seven_days_ago:
                calls = int(user.total_calls)
                if calls > 100:
                    days_since_registration = (now - user.created_at).days + 1
                    calls_per_day = calls / days_since_registration
                    anomalies.append({
                        "type": "new_user_spike",
                        "user_id": user.id,
                        "username": user.username,
                        "value": calls,
                        "days_since_registration": days_since_registration,
                        "calls_per_day": round(calls_per_day, 2),
                        "severity": "high" if calls > 500 else "medium"
                    })

    return {"anomalies": anomalies}
