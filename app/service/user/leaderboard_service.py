"""
Leaderboard service for calculating user rankings across multiple metrics.

This module provides comprehensive ranking calculations for:
- Online time
- Total API queries
- Category-based query counts (4 categories)
- Individual endpoint usage (13 endpoints)
"""

from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.service.auth import models

# Category definitions - exact path matching
CATEGORY_PATHS = {
    "category_音韻查詢": ["/api/ZhongGu", "/api/YinWei", "/api/phonology", "/api/charlist", "/api/feature_stats", "/api/compare/ZhongGu"],
    "category_字調查詢": ["/api/search_chars/", "/api/search_tones/", "/api/compare/chars", "/api/compare/tones"],
    "category_音系分析": [
        "/api/phonology_matrix",
        "/api/phonology_classification_matrix",
        "/api/feature_counts"
    ],
    "category_工具使用": [
        "/api/tools/check/analyze",
        "/api/tools/jyut2ipa/process",
        "/api/tools/merge/execute",
        "/api/tools/praat/jobs"
    ],
    "category_其他查询": [
        "/sql/query",
        "/sql/tree/full",
        "/api/get_coordinates",
    ],
}

# Individual endpoint rankings - exact path matching
ENDPOINT_PATHS = [
    "/api/ZhongGu",
    "/api/YinWei",
    "/api/phonology",
    "/api/charlist",
    "/api/search_chars/",
    "/api/search_tones/",
    "/api/compare/ZhongGu",
    "/api/compare/chars",
    "/api/compare/tones",
    "/api/phonology_matrix",
    "/api/phonology_classification_matrix",
    "/api/feature_counts",
    "/api/feature_stats",
    "/api/tools/check/analyze",
    "/api/tools/jyut2ipa/upload",
    "/api/tools/merge/execute",
    "/api/tools/praat/jobs",
    "/sql/query",
    "/sql/tree/full",
    "/api/get_coordinates",
]


class RankingDetail:
    """Individual ranking detail"""
    def __init__(self, rank: Optional[int], value: int, gap_to_prev: Optional[int], first_place_value: int):
        self.rank = rank
        self.value = value
        self.gap_to_prev = gap_to_prev
        self.first_place_value = first_place_value


def _calculate_online_time_rank(db: Session, user_id: int) -> RankingDetail:
    """
    Calculate ranking based on total online time.

    Args:
        db: Database session
        user_id: User ID to calculate rank for

    Returns:
        RankingDetail with rank, value, gap_to_prev, and first_place_value
    """
    # Get user's online time
    user = db.query(models.User).filter(models.User.id == user_id).first()
    user_value = user.total_online_seconds if user else 0

    # Get first place value
    first_place_value = db.query(func.max(models.User.total_online_seconds)).scalar() or 0

    if user_value == 0:
        # User has no activity, but should still have a rank
        # Rank = (number of users with positive values) + 1
        rank = db.query(func.count(models.User.id)).filter(
            models.User.total_online_seconds > 0
        ).scalar() + 1

        # gap_to_prev = smallest positive value - 0
        prev_value = db.query(models.User.total_online_seconds).filter(
            models.User.total_online_seconds > 0
        ).order_by(models.User.total_online_seconds.asc()).first()

        gap_to_prev = prev_value[0] if prev_value else None

        return RankingDetail(rank=rank, value=0, gap_to_prev=gap_to_prev, first_place_value=first_place_value)

    # Calculate rank using standard competition ranking
    # Count users with higher values
    rank = db.query(func.count(models.User.id)).filter(
        models.User.total_online_seconds > user_value
    ).scalar() + 1

    # Get previous rank value (for gap calculation)
    prev_value = db.query(models.User.total_online_seconds).filter(
        models.User.total_online_seconds > user_value
    ).order_by(models.User.total_online_seconds.asc()).first()

    gap_to_prev = None if prev_value is None else prev_value[0] - user_value

    return RankingDetail(rank=rank, value=user_value, gap_to_prev=gap_to_prev, first_place_value=first_place_value)


def _calculate_total_queries_rank(db: Session, user_id: int) -> RankingDetail:
    """
    Calculate ranking based on total API queries across all endpoints.

    Args:
        db: Database session
        user_id: User ID to calculate rank for

    Returns:
        RankingDetail with rank, value, gap_to_prev, and first_place_value
    """
    # Get user's total query count
    user_total = db.query(func.sum(models.ApiUsageSummary.count)).filter(
        models.ApiUsageSummary.user_id == user_id
    ).scalar() or 0

    # Calculate rank by counting users with higher totals
    # Use subquery to get per-user totals
    user_totals = db.query(
        models.ApiUsageSummary.user_id,
        func.sum(models.ApiUsageSummary.count).label('total')
    ).group_by(models.ApiUsageSummary.user_id).subquery()

    # Get first place value
    first_place_value = db.query(func.max(user_totals.c.total)).scalar() or 0

    if user_total == 0:
        # User has no activity, but should still have a rank
        # Rank = (number of users with positive values) + 1
        rank = db.query(func.count(user_totals.c.total)).filter(
            user_totals.c.total > 0
        ).scalar() + 1

        # gap_to_prev = smallest positive value - 0
        prev_value = db.query(user_totals.c.total).filter(
            user_totals.c.total > 0
        ).order_by(user_totals.c.total.asc()).first()

        gap_to_prev = prev_value[0] if prev_value else None

        return RankingDetail(rank=rank, value=0, gap_to_prev=gap_to_prev, first_place_value=first_place_value)

    rank = db.query(func.count(user_totals.c.total)).filter(
        user_totals.c.total > user_total
    ).scalar() + 1

    # Get previous rank value
    prev_value = db.query(user_totals.c.total).filter(
        user_totals.c.total > user_total
    ).order_by(user_totals.c.total.asc()).first()

    gap_to_prev = None if prev_value is None else prev_value[0] - user_total

    return RankingDetail(rank=rank, value=user_total, gap_to_prev=gap_to_prev, first_place_value=first_place_value)


def _calculate_category_rank(db: Session, user_id: int, category_name: str, paths: List[str]) -> RankingDetail:
    """
    Calculate ranking based on aggregated query count for a category of endpoints.

    Args:
        db: Database session
        user_id: User ID to calculate rank for
        category_name: Name of the category (for logging)
        paths: List of exact API paths to include in this category

    Returns:
        RankingDetail with rank, value, gap_to_prev, and first_place_value
    """
    # Get user's total for this category
    user_total = db.query(func.sum(models.ApiUsageSummary.count)).filter(
        and_(
            models.ApiUsageSummary.user_id == user_id,
            models.ApiUsageSummary.path.in_(paths)
        )
    ).scalar() or 0

    # Calculate rank
    user_totals = db.query(
        models.ApiUsageSummary.user_id,
        func.sum(models.ApiUsageSummary.count).label('total')
    ).filter(
        models.ApiUsageSummary.path.in_(paths)
    ).group_by(models.ApiUsageSummary.user_id).subquery()

    # Get first place value
    first_place_value = db.query(func.max(user_totals.c.total)).scalar() or 0

    if user_total == 0:
        # User has no activity, but should still have a rank
        # Rank = (number of users with positive values) + 1
        rank = db.query(func.count(user_totals.c.total)).filter(
            user_totals.c.total > 0
        ).scalar() + 1

        # gap_to_prev = smallest positive value - 0
        prev_value = db.query(user_totals.c.total).filter(
            user_totals.c.total > 0
        ).order_by(user_totals.c.total.asc()).first()

        gap_to_prev = prev_value[0] if prev_value else None

        return RankingDetail(rank=rank, value=0, gap_to_prev=gap_to_prev, first_place_value=first_place_value)

    rank = db.query(func.count(user_totals.c.total)).filter(
        user_totals.c.total > user_total
    ).scalar() + 1

    # Get previous rank value
    prev_value = db.query(user_totals.c.total).filter(
        user_totals.c.total > user_total
    ).order_by(user_totals.c.total.asc()).first()

    gap_to_prev = None if prev_value is None else prev_value[0] - user_total

    return RankingDetail(rank=rank, value=user_total, gap_to_prev=gap_to_prev, first_place_value=first_place_value)

def _calculate_endpoint_rank(db: Session, user_id: int, endpoint_path: str) -> RankingDetail:
    """
    Calculate ranking based on query count for a specific endpoint.

    Args:
        db: Database session
        user_id: User ID to calculate rank for
        endpoint_path: Exact API path to rank by

    Returns:
        RankingDetail with rank, value, gap_to_prev, and first_place_value
    """
    # Get user's count for this endpoint
    user_record = db.query(models.ApiUsageSummary).filter(
        and_(
            models.ApiUsageSummary.user_id == user_id,
            models.ApiUsageSummary.path == endpoint_path
        )
    ).first()

    user_value = user_record.count if user_record else 0

    # Get first place value
    first_place_value = db.query(func.max(models.ApiUsageSummary.count)).filter(
        models.ApiUsageSummary.path == endpoint_path
    ).scalar() or 0

    if user_value == 0:
        # User has no activity, but should still have a rank
        # Rank = (number of users with positive values) + 1
        rank = db.query(func.count(models.ApiUsageSummary.user_id)).filter(
            and_(
                models.ApiUsageSummary.path == endpoint_path,
                models.ApiUsageSummary.count > 0
            )
        ).scalar() + 1

        # gap_to_prev = smallest positive value - 0
        prev_value = db.query(models.ApiUsageSummary.count).filter(
            and_(
                models.ApiUsageSummary.path == endpoint_path,
                models.ApiUsageSummary.count > 0
            )
        ).order_by(models.ApiUsageSummary.count.asc()).first()

        gap_to_prev = prev_value[0] if prev_value else None

        return RankingDetail(rank=rank, value=0, gap_to_prev=gap_to_prev, first_place_value=first_place_value)

    # Calculate rank
    rank = db.query(func.count(models.ApiUsageSummary.user_id)).filter(
        and_(
            models.ApiUsageSummary.path == endpoint_path,
            models.ApiUsageSummary.count > user_value
        )
    ).scalar() + 1

    # Get previous rank value
    prev_value = db.query(models.ApiUsageSummary.count).filter(
        and_(
            models.ApiUsageSummary.path == endpoint_path,
            models.ApiUsageSummary.count > user_value
        )
    ).order_by(models.ApiUsageSummary.count.asc()).first()

    gap_to_prev = None if prev_value is None else prev_value[0] - user_value

    return RankingDetail(rank=rank, value=user_value, gap_to_prev=gap_to_prev, first_place_value=first_place_value)


def get_user_leaderboard(db: Session, user_id: int) -> Dict[str, Dict]:
    """
    Calculate all 18 rankings for a user in a single call.

    This function computes:
    - 1 online time ranking
    - 1 total queries ranking
    - 4 category rankings
    - 13 individual endpoint rankings

    Args:
        db: Database session
        user_id: User ID to calculate rankings for

    Returns:
        Dictionary with 'rankings' and 'total_users' keys
        Each ranking contains: rank, value, gap_to_prev, first_place_value
    """
    rankings = {}

    # 1. Online time ranking
    rankings["online_time"] = _calculate_online_time_rank(db, user_id)

    # 2. Total queries ranking
    rankings["total_queries"] = _calculate_total_queries_rank(db, user_id)

    # 3. Category rankings
    for category_name, paths in CATEGORY_PATHS.items():
        rankings[category_name] = _calculate_category_rank(db, user_id, category_name, paths)

    # 4. Individual endpoint rankings
    for endpoint_path in ENDPOINT_PATHS:
        # Create a safe key name by replacing special characters
        key_name = f"endpoint_{endpoint_path.replace('/', '_').replace(':', '_')}"
        rankings[key_name] = _calculate_endpoint_rank(db, user_id, endpoint_path)

    # Calculate total active users (users with any activity)
    total_users = db.query(func.count(func.distinct(models.User.id))).filter(
        models.User.total_online_seconds > 0
    ).scalar()

    # Convert RankingDetail objects to dictionaries
    rankings_dict = {}
    for key, detail in rankings.items():
        rankings_dict[key] = {
            "rank": detail.rank,
            "value": detail.value,
            "gap_to_prev": detail.gap_to_prev,
            "first_place_value": detail.first_place_value
        }

    return {
        "rankings": rankings_dict,
        "total_users": total_users
    }
