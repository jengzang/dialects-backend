"""
API Diversity Analysis Module

Analyzes how diverse users' API usage patterns are.
"""

import math
from typing import List
from sqlalchemy.orm import Session

from app.service.auth.models import User, ApiUsageSummary


def calculate_shannon_entropy(api_usage_list: List[tuple]) -> float:
    """
    Calculate Shannon entropy for API usage distribution.

    Shannon Entropy: H = -Σ(p_i * log2(p_i))
    where p_i is the proportion of calls to API i

    Higher entropy = more diverse usage (explorer)
    Lower entropy = more concentrated usage (focused)

    Args:
        api_usage_list: List of (path, count) tuples

    Returns:
        Shannon entropy value
    """
    if not api_usage_list:
        return 0.0

    total_calls = sum(count for _, count in api_usage_list)
    if total_calls == 0:
        return 0.0

    entropy = 0.0
    for _, count in api_usage_list:
        if count > 0:
            p_i = count / total_calls
            entropy -= p_i * math.log2(p_i)

    return entropy


def get_api_diversity(
    db: Session,
    sort_by: str = "diversity"
) -> dict:
    """
    Analyze API usage diversity for each user using Shannon entropy.

    Args:
        db: Database session
        sort_by: Sort by 'diversity' or 'calls'

    Returns:
        Dictionary with diversity analysis
    """
    # Get all users with API usage
    users_with_usage = db.query(User.id, User.username).join(
        ApiUsageSummary, User.id == ApiUsageSummary.user_id
    ).distinct().all()

    users = []
    explorer_count = 0
    focused_count = 0
    total_entropy = 0

    for user in users_with_usage:
        user_id = user.id
        username = user.username

        # Get detailed API usage for this user
        api_usage = db.query(
            ApiUsageSummary.path,
            ApiUsageSummary.count
        ).filter(
            ApiUsageSummary.user_id == user_id
        ).all()

        api_count = len(api_usage)
        total_calls = sum(usage.count for usage in api_usage)

        # Calculate Shannon entropy as diversity score
        diversity_score = calculate_shannon_entropy(api_usage)

        # Classify user type based on entropy
        # Entropy thresholds:
        # - High entropy (> 2.0): Explorer (diverse usage)
        # - Low entropy (<= 2.0): Focused (concentrated usage)
        #
        # Reference values:
        # - 1 API only: entropy = 0
        # - 2 APIs (50/50): entropy = 1.0
        # - 4 APIs (equal): entropy = 2.0
        # - 8 APIs (equal): entropy = 3.0
        # - 16 APIs (equal): entropy = 4.0
        user_type = "探索型" if diversity_score > 2.0 else "专注型"

        if user_type == "探索型":
            explorer_count += 1
        else:
            focused_count += 1

        total_entropy += diversity_score

        users.append({
            "user_id": user_id,
            "username": username,
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
    avg_diversity = total_entropy / len(users) if users else 0

    return {
        "users": users,
        "summary": {
            "total_users": len(users),
            "avg_diversity": round(avg_diversity, 4),
            "explorer_count": explorer_count,
            "focused_count": focused_count
        }
    }
