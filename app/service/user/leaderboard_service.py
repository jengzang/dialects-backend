"""
Leaderboard service for calculating user rankings across multiple metrics.

This module provides ranking calculations for:
- Online time
- Total API queries
- Category-based query counts
- Grouped endpoint aggregates
- Individual endpoint usage
"""

from typing import Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.service.auth.database import models

RuleConfig = Dict[str, List[str]]

VILLAGES_ML_RULE: RuleConfig = {
    "paths": [],
    "prefixes": ["/api/villages/"],
    "exclude_prefixes": ["/api/villages/admin/"],
}

PHO_PIE_RULE: RuleConfig = {
    "paths": ["/api/pho_pie_by_value", "/api/pho_pie_by_status"],
    "prefixes": [],
    "exclude_prefixes": [],
}

LOCATIONS_RULE: RuleConfig = {
    "paths": ["/api/locations/detail", "/api/locations/partitions"],
    "prefixes": [],
    "exclude_prefixes": [],
}

# Category definitions support exact path matching plus optional prefix rules.
CATEGORY_RULES: Dict[str, RuleConfig] = {
    "category_音韻查詢": {
        "paths": [
            "/api/ZhongGu",
            "/api/YinWei",
            "/api/phonology",
            "/api/charlist",
            "/api/feature_stats",
            "/api/compare/ZhongGu",
        ],
        "prefixes": [],
        "exclude_prefixes": [],
    },
    "category_字調查詢": {
        "paths": [
            "/api/search_chars/",
            "/api/search_tones/",
            "/api/compare/chars",
            "/api/compare/tones",
        ],
        "prefixes": [],
        "exclude_prefixes": [],
    },
    "category_音系分析": {
        "paths": [
            "/api/phonology_matrix",
            "/api/phonology_classification_matrix",
            "/api/feature_counts",
            "/api/pho_pie_by_value",
            "/api/pho_pie_by_status",
        ],
        "prefixes": [],
        "exclude_prefixes": [],
    },
    "category_工具使用": {
        "paths": [
            "/api/tools/check/analyze",
            "/api/tools/jyut2ipa/process",
            "/api/tools/merge/execute",
            "/api/tools/praat/jobs",
        ],
        "prefixes": [],
        "exclude_prefixes": [],
    },
    "category_其他查询": {
        "paths": [
            "/sql/query",
            "/sql/tree/full",
            "/api/get_coordinates",
        ],
        "prefixes": ["/api/villages/","/api/locations/"],
        "exclude_prefixes": ["/api/villages/admin/"],
    },
}

AGGREGATED_ENDPOINT_RULES: Dict[str, RuleConfig] = {
    "endpoint_group_villages_ml": VILLAGES_ML_RULE,
    "endpoint_group_pho_pie": PHO_PIE_RULE,
    "endpoint_group_locations": LOCATIONS_RULE,
}

# Individual endpoint rankings - exact path matching.
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
    """Individual ranking detail."""

    def __init__(self, rank: Optional[int], value: int, gap_to_prev: Optional[int], first_place_value: int):
        self.rank = rank
        self.value = value
        self.gap_to_prev = gap_to_prev
        self.first_place_value = first_place_value


def _build_usage_filter(rule: RuleConfig):
    """Build a SQLAlchemy filter from exact paths and path prefixes."""
    include_conditions = []

    exact_paths = rule.get("paths", [])
    if exact_paths:
        include_conditions.append(models.ApiUsageSummary.path.in_(exact_paths))

    for prefix in rule.get("prefixes", []):
        include_conditions.append(models.ApiUsageSummary.path.like(f"{prefix}%"))

    if not include_conditions:
        return models.ApiUsageSummary.path == "__never_match__"

    include_filter = include_conditions[0] if len(include_conditions) == 1 else or_(*include_conditions)
    exclude_conditions = [
        ~models.ApiUsageSummary.path.like(f"{prefix}%")
        for prefix in rule.get("exclude_prefixes", [])
    ]

    return and_(include_filter, *exclude_conditions) if exclude_conditions else include_filter


def _build_exact_path_rule(path: str) -> RuleConfig:
    """Create a rule config for a single exact API path."""
    return {
        "paths": [path],
        "prefixes": [],
        "exclude_prefixes": [],
    }


def _rank_from_totals(db: Session, user_total: int, user_totals) -> RankingDetail:
    """Calculate ranking metrics from a per-user totals subquery."""
    first_place_value = db.query(func.max(user_totals.c.total)).scalar() or 0

    if user_total == 0:
        rank = db.query(func.count(user_totals.c.total)).filter(
            user_totals.c.total > 0
        ).scalar() + 1

        prev_value = db.query(user_totals.c.total).filter(
            user_totals.c.total > 0
        ).order_by(user_totals.c.total.asc()).first()

        gap_to_prev = prev_value[0] if prev_value else None
        return RankingDetail(rank=rank, value=0, gap_to_prev=gap_to_prev, first_place_value=first_place_value)

    rank = db.query(func.count(user_totals.c.total)).filter(
        user_totals.c.total > user_total
    ).scalar() + 1

    prev_value = db.query(user_totals.c.total).filter(
        user_totals.c.total > user_total
    ).order_by(user_totals.c.total.asc()).first()

    gap_to_prev = None if prev_value is None else prev_value[0] - user_total
    return RankingDetail(rank=rank, value=user_total, gap_to_prev=gap_to_prev, first_place_value=first_place_value)


def _calculate_online_time_rank(db: Session, user_id: int) -> RankingDetail:
    """Calculate ranking based on total online time."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    user_value = user.total_online_seconds if user else 0

    first_place_value = db.query(func.max(models.User.total_online_seconds)).scalar() or 0

    if user_value == 0:
        rank = db.query(func.count(models.User.id)).filter(
            models.User.total_online_seconds > 0
        ).scalar() + 1

        prev_value = db.query(models.User.total_online_seconds).filter(
            models.User.total_online_seconds > 0
        ).order_by(models.User.total_online_seconds.asc()).first()

        gap_to_prev = prev_value[0] if prev_value else None
        return RankingDetail(rank=rank, value=0, gap_to_prev=gap_to_prev, first_place_value=first_place_value)

    rank = db.query(func.count(models.User.id)).filter(
        models.User.total_online_seconds > user_value
    ).scalar() + 1

    prev_value = db.query(models.User.total_online_seconds).filter(
        models.User.total_online_seconds > user_value
    ).order_by(models.User.total_online_seconds.asc()).first()

    gap_to_prev = None if prev_value is None else prev_value[0] - user_value
    return RankingDetail(rank=rank, value=user_value, gap_to_prev=gap_to_prev, first_place_value=first_place_value)


def _calculate_total_queries_rank(db: Session, user_id: int) -> RankingDetail:
    """Calculate ranking based on total API queries across all endpoints."""
    user_total = db.query(func.sum(models.ApiUsageSummary.count)).filter(
        models.ApiUsageSummary.user_id == user_id
    ).scalar() or 0

    user_totals = db.query(
        models.ApiUsageSummary.user_id,
        func.sum(models.ApiUsageSummary.count).label("total"),
    ).group_by(models.ApiUsageSummary.user_id).subquery()

    return _rank_from_totals(db, user_total, user_totals)


def _calculate_aggregate_rank(db: Session, user_id: int, rule: RuleConfig) -> RankingDetail:
    """Calculate ranking based on aggregated query count for a rule of endpoints."""
    usage_filter = _build_usage_filter(rule)

    user_total = db.query(func.sum(models.ApiUsageSummary.count)).filter(
        and_(
            models.ApiUsageSummary.user_id == user_id,
            usage_filter,
        )
    ).scalar() or 0

    user_totals = db.query(
        models.ApiUsageSummary.user_id,
        func.sum(models.ApiUsageSummary.count).label("total"),
    ).filter(
        usage_filter
    ).group_by(models.ApiUsageSummary.user_id).subquery()

    return _rank_from_totals(db, user_total, user_totals)


def _calculate_endpoint_rank(db: Session, user_id: int, endpoint_path: str) -> RankingDetail:
    """Calculate ranking based on query count for one exact endpoint."""
    return _calculate_aggregate_rank(db, user_id, _build_exact_path_rule(endpoint_path))


def get_user_leaderboard(db: Session, user_id: int) -> Dict[str, Dict]:
    """
    Calculate all rankings for a user in a single call.

    This function computes:
    - 1 online time ranking
    - 1 total queries ranking
    - 5 category rankings
    - 2 grouped endpoint rankings
    - individual endpoint rankings
    """
    rankings = {}

    rankings["online_time"] = _calculate_online_time_rank(db, user_id)
    rankings["total_queries"] = _calculate_total_queries_rank(db, user_id)

    for category_name, rule in CATEGORY_RULES.items():
        rankings[category_name] = _calculate_aggregate_rank(db, user_id, rule)

    for group_name, rule in AGGREGATED_ENDPOINT_RULES.items():
        rankings[group_name] = _calculate_aggregate_rank(db, user_id, rule)

    for endpoint_path in ENDPOINT_PATHS:
        key_name = f"endpoint_{endpoint_path.replace('/', '_').replace(':', '_')}"
        rankings[key_name] = _calculate_endpoint_rank(db, user_id, endpoint_path)

    total_users = db.query(func.count(func.distinct(models.User.id))).filter(
        models.User.total_online_seconds > 0
    ).scalar()

    rankings_dict = {}
    for key, detail in rankings.items():
        rankings_dict[key] = {
            "rank": detail.rank,
            "value": detail.value,
            "gap_to_prev": detail.gap_to_prev,
            "first_place_value": detail.first_place_value,
        }

    return {
        "rankings": rankings_dict,
        "total_users": total_users,
    }
