"""
API Diversity Analysis Module

Analyzes how diverse users' API usage patterns are.
"""

from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.models import User, ApiUsageSummary


def get_api_diversity(
    db: Session,
    sort_by: str = "diversity"
) -> dict:
    """
    Analyze API usage diversity for each user.

    Args:
        db: Database session
        sort_by: Sort by 'diversity' or 'calls'

    Returns:
        Dictionary with diversity analysis
    """
    # Get user API usage
    user_api_usage = db.query(
        User.id,
        User.username,
        func.count(ApiUsageSummary.path.distinct()).label('api_count'),
        func.sum(ApiUsageSummary.count).label('total_calls')
    ).join(
        ApiUsageSummary, User.id == ApiUsageSummary.user_id
    ).group_by(User.id).all()

    users = []
    explorer_count = 0
    focused_count = 0
    total_diversity = 0

    for user in user_api_usage:
        api_count = int(user.api_count)
        total_calls = int(user.total_calls)

        # Calculate diversity score
        diversity_score = api_count / total_calls if total_calls > 0 else 0

        # Classify user type
        # Explorer: diversity > 0.01 (uses many different APIs)
        # Focused: diversity <= 0.01 (concentrates on few APIs)
        user_type = "探索型" if diversity_score > 0.01 else "专注型"

        if user_type == "探索型":
            explorer_count += 1
        else:
            focused_count += 1

        total_diversity += diversity_score

        users.append({
            "user_id": user.id,
            "username": user.username,
            "api_count": api_count,
            "total_calls": total_calls,
            "diversity_score": round(diversity_score, 4),
            "user_type": user_type
        })

    # Sort users
    if sort_by == "diversity":
        users.sort(key=lambda x: x["diversity_score"], reverse=True)
    else:  # sort by calls
        users.sort(key=lambda x: x["total_calls"], reverse=True)

    # Calculate summary
    avg_diversity = total_diversity / len(users) if users else 0

    return {
        "users": users,
        "summary": {
            "total_users": len(users),
            "avg_diversity": round(avg_diversity, 4),
            "explorer_count": explorer_count,
            "focused_count": focused_count
        }
    }
