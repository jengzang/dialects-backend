"""
RFM (Recency, Frequency, Monetary) User Value Analysis Module

Analyzes user value based on:
- R (Recency): Days since last activity
- F (Frequency): Total API calls
- M (Monetary): Total duration + traffic
"""

from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.common.time_utils import to_shanghai_iso
from app.service.auth.database.models import User, ApiUsageSummary


def calculate_rfm_score(recency_days: int, frequency: int, monetary: float,
                        r_thresholds: tuple, f_thresholds: tuple, m_thresholds: tuple) -> tuple:
    """
    Calculate RFM scores (1-5 scale, 5 is best).

    Args:
        recency_days: Days since last activity
        frequency: Total API calls
        monetary: Monetary value
        r_thresholds: (p20, p40, p60, p80) for recency
        f_thresholds: (p20, p40, p60, p80) for frequency
        m_thresholds: (p20, p40, p60, p80) for monetary

    Returns:
        Tuple of (r_score, f_score, m_score)
    """
    # Recency: lower is better (reverse scoring)
    if recency_days <= r_thresholds[0]:
        r_score = 5
    elif recency_days <= r_thresholds[1]:
        r_score = 4
    elif recency_days <= r_thresholds[2]:
        r_score = 3
    elif recency_days <= r_thresholds[3]:
        r_score = 2
    else:
        r_score = 1

    # Frequency: higher is better
    if frequency >= f_thresholds[3]:
        f_score = 5
    elif frequency >= f_thresholds[2]:
        f_score = 4
    elif frequency >= f_thresholds[1]:
        f_score = 3
    elif frequency >= f_thresholds[0]:
        f_score = 2
    else:
        f_score = 1

    # Monetary: higher is better
    if monetary >= m_thresholds[3]:
        m_score = 5
    elif monetary >= m_thresholds[2]:
        m_score = 4
    elif monetary >= m_thresholds[1]:
        m_score = 3
    elif monetary >= m_thresholds[0]:
        m_score = 2
    else:
        m_score = 1

    return r_score, f_score, m_score


def classify_rfm_segment(r_score: int, f_score: int, m_score: int) -> str:
    """
    Classify user into RFM segment.

    Segments:
    - VIP: R>=4, F>=4, M>=4
    - Potential: R>=4, F>=3, M>=3
    - New: R>=4, F<=2, M<=2
    - Dormant High Value: R<=2, F>=4, M>=4
    - Low Value: R<=2, F<=2, M<=2
    - Others: Everything else
    """
    if r_score >= 4 and f_score >= 4 and m_score >= 4:
        return "VIP"
    elif r_score >= 4 and f_score >= 3 and m_score >= 3:
        return "Potential"
    elif r_score >= 4 and f_score <= 2 and m_score <= 2:
        return "New"
    elif r_score <= 2 and f_score >= 4 and m_score >= 4:
        return "Dormant High Value"
    elif r_score <= 2 and f_score <= 2 and m_score <= 2:
        return "Low Value"
    else:
        return "Others"


def get_rfm_analysis(db: Session, include_users: bool = False) -> dict:
    """
    Perform RFM analysis on users.

    Args:
        db: Database session
        include_users: Whether to include user details

    Returns:
        Dictionary with RFM segment statistics
    """
    now = datetime.utcnow()

    # Get user statistics
    user_stats = db.query(
        User.id,
        User.username,
        User.last_seen,
        func.coalesce(func.sum(ApiUsageSummary.count), 0).label('frequency'),
        func.coalesce(func.sum(ApiUsageSummary.total_duration), 0).label('total_duration'),
        func.coalesce(func.sum(ApiUsageSummary.total_upload), 0).label('total_upload'),
        func.coalesce(func.sum(ApiUsageSummary.total_download), 0).label('total_download')
    ).outerjoin(
        ApiUsageSummary, User.id == ApiUsageSummary.user_id
    ).group_by(User.id).all()

    # Calculate RFM values
    rfm_data = []
    for user in user_stats:
        recency_days = (now - user.last_seen).days if user.last_seen else 999
        frequency = int(user.frequency)
        # Monetary = duration + (upload + download) / 1000
        monetary = float(user.total_duration) + (float(user.total_upload) + float(user.total_download)) / 1000

        rfm_data.append({
            "user_id": user.id,
            "username": user.username,
            "recency_days": recency_days,
            "frequency": frequency,
            "monetary": round(monetary, 2),
            "last_seen": to_shanghai_iso(user.last_seen) if user.last_seen else None
        })

    # Calculate thresholds (20th, 40th, 60th, 80th percentiles)
    if not rfm_data:
        return {"segments": [], "summary": {}}

    recency_values = [d["recency_days"] for d in rfm_data]
    frequency_values = [d["frequency"] for d in rfm_data]
    monetary_values = [d["monetary"] for d in rfm_data]

    def get_percentiles(values):
        sorted_values = sorted(values)
        n = len(sorted_values)
        return (
            sorted_values[int(n * 0.2)],
            sorted_values[int(n * 0.4)],
            sorted_values[int(n * 0.6)],
            sorted_values[int(n * 0.8)]
        )

    r_thresholds = get_percentiles(recency_values)
    f_thresholds = get_percentiles(frequency_values)
    m_thresholds = get_percentiles(monetary_values)

    # Calculate RFM scores and classify
    segments = {}
    for data in rfm_data:
        r_score, f_score, m_score = calculate_rfm_score(
            data["recency_days"], data["frequency"], data["monetary"],
            r_thresholds, f_thresholds, m_thresholds
        )
        segment = classify_rfm_segment(r_score, f_score, m_score)

        data["r_score"] = r_score
        data["f_score"] = f_score
        data["m_score"] = m_score
        data["segment"] = segment

        if segment not in segments:
            segments[segment] = {
                "users": [],
                "count": 0,
                "total_recency": 0,
                "total_frequency": 0,
                "total_monetary": 0
            }

        segments[segment]["users"].append(data)
        segments[segment]["count"] += 1
        segments[segment]["total_recency"] += data["recency_days"]
        segments[segment]["total_frequency"] += data["frequency"]
        segments[segment]["total_monetary"] += data["monetary"]

    # Build result
    result = {"segments": []}
    for segment_name, segment_data in segments.items():
        count = segment_data["count"]
        segment_info = {
            "segment": segment_name,
            "count": count,
            "avg_recency_days": round(segment_data["total_recency"] / count, 2),
            "avg_frequency": round(segment_data["total_frequency"] / count, 2),
            "avg_monetary": round(segment_data["total_monetary"] / count, 2)
        }

        if include_users:
            segment_info["users"] = segment_data["users"]

        result["segments"].append(segment_info)

    return result
