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

from sqlalchemy import text
from sqlalchemy.orm import Session

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
    "paths": ["/api/locations/detail", "/api/locations/partitions", "/api/locations/points"],
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
    "category_詞句查詢": {
        "paths": [
            "/api/vocabulary/search/entries",
            "/api/vocabulary/search/map-points",
            "/api/vocabulary/search/standard-words",
            "/api/vocabulary/search/map-items",
            "/api/vocabulary/search/location-options",
            "/api/vocabulary/logs",
            "/api/vocabulary/imports",
            "/api/vocabulary/imports/preview",
            "/api/vocabulary/sql/query",
            "/api/vocabulary/sql/mutate",
            "/api/vocabulary/sql/batch-mutate",
            "/api/vocabulary/sql/batch-replace-preview",
            "/api/vocabulary/sql/batch-replace-execute",
        ],
        "prefixes": ["/api/yubao/", "/api/vocabulary/locations/"],
        "exclude_prefixes": [],
    },
    "category_工具使用": {
        "paths": [
            "/api/tools/praat/jobs",
        ],
        "prefixes": ["/api/tools/check/", "/api/tools/jyut2ipa/", "/api/tools/merge/"],
        "exclude_prefixes": [],
    },
    "category_其他查询": {
        "paths": [
            "/sql/query",
            "/sql/tree/full",
            "/sql/tree/lazy",
        ],
        "prefixes": [],
        "exclude_prefixes": [],
    },
    "category_用户自定义": {
        "paths": [
            "/api/custom_regions",
            "/api/submit_form",
            "/api/delete_form",
        ],
        "prefixes": ["/user/custom/"],
        "exclude_prefixes": [],
    },
    "category_地理村落": {
        "paths": [
            "/api/toponyms/points",
            "/api/toponyms/names",
            "/api/toponyms/details",
            "/api/toponyms/divisions",
            "/api/locations/detail",
            "/api/locations/partitions",
            "/api/locations/points",
            "/api/get_coordinates",
        ],
        "prefixes": ["/api/villages/", "/api/gis/"],
        "exclude_prefixes": ["/api/villages/admin/"],
    },
}

SQL_TREE_RULE: RuleConfig = {
    "paths": ["/sql/tree/full", "/sql/tree/lazy"],
    "prefixes": [],
    "exclude_prefixes": [],
}

YUBAO_RULE: RuleConfig = {
    "paths": [],
    "prefixes": ["/api/yubao/"],
    "exclude_prefixes": [],
}

VOCABULARY_SEARCH_RULE: RuleConfig = {
    "paths": [
        "/api/vocabulary/search/entries",
        "/api/vocabulary/search/map-points",
        "/api/vocabulary/search/standard-words",
        "/api/vocabulary/search/map-items",
        "/api/vocabulary/search/location-options",
    ],
    "prefixes": [],
    "exclude_prefixes": [],
}

VOCABULARY_TABLE_RULE: RuleConfig = {
    "paths": [
        "/api/vocabulary/sql/query",
    ],
    "prefixes": [],
    "exclude_prefixes": [],
}

VOCABULARY_EDIT_RULE: RuleConfig = {
    "paths": [
        "/api/vocabulary/logs",
        "/api/vocabulary/imports",
        "/api/vocabulary/imports/preview",
        "/api/vocabulary/sql/mutate",
        "/api/vocabulary/sql/batch-mutate",
        "/api/vocabulary/sql/batch-replace-preview",
        "/api/vocabulary/sql/batch-replace-execute",
    ],
    "prefixes": ["/api/vocabulary/locations/"],
    "exclude_prefixes": [],
}

CUSTOM_REGIONS_RULE: RuleConfig = {
    "paths": ["/api/custom_regions"],
    "prefixes": [],
    "exclude_prefixes": [],
}

CUSTOM_DATA_QUERY_RULE: RuleConfig = {
    "paths": [
        "/user/custom/points",
        "/user/custom/features",
        "/user/custom/data-by-point",
        "/user/custom/data-by-feature",
    ],
    "prefixes": [],
    "exclude_prefixes": [],
}

CUSTOM_DATA_EDIT_RULE: RuleConfig = {
    "paths": [
        "/user/custom/batch-create",
        "/user/custom/edit",
        "/user/custom/batch-delete",
        "/api/submit_form",
        "/api/delete_form",
    ],
    "prefixes": [],
    "exclude_prefixes": [],
}

TOPONYMS_RULE: RuleConfig = {
    "paths": [
        "/api/toponyms/points",
        "/api/toponyms/names",
        "/api/toponyms/details",
        "/api/toponyms/divisions",
    ],
    "prefixes": [],
    "exclude_prefixes": [],
}

GIS_RULE: RuleConfig = {
    "paths": [],
    "prefixes": ["/api/gis/"],
    "exclude_prefixes": [],
}

TOOLS_CHECK_RULE: RuleConfig = {
    "paths": [],
    "prefixes": ["/api/tools/check/"],
    "exclude_prefixes": [],
}

TOOLS_JYUT2IPA_RULE: RuleConfig = {
    "paths": [],
    "prefixes": ["/api/tools/jyut2ipa/"],
    "exclude_prefixes": [],
}

TOOLS_MERGE_RULE: RuleConfig = {
    "paths": [],
    "prefixes": ["/api/tools/merge/"],
    "exclude_prefixes": [],
}

AGGREGATED_ENDPOINT_RULES: Dict[str, RuleConfig] = {
    "endpoint_group_villages_ml": VILLAGES_ML_RULE,
    "endpoint_group_pho_pie": PHO_PIE_RULE,
    "endpoint_group_locations": LOCATIONS_RULE,
    "endpoint_group_sql_tree": SQL_TREE_RULE,
    "endpoint_group_yubao": YUBAO_RULE,
    "endpoint_group_vocabulary_search": VOCABULARY_SEARCH_RULE,
    "endpoint_group_vocabulary_table": VOCABULARY_TABLE_RULE,
    "endpoint_group_vocabulary_edit": VOCABULARY_EDIT_RULE,
    "endpoint_group_custom_regions": CUSTOM_REGIONS_RULE,
    "endpoint_group_custom_data_query": CUSTOM_DATA_QUERY_RULE,
    "endpoint_group_custom_data_edit": CUSTOM_DATA_EDIT_RULE,
    "endpoint_group_toponyms": TOPONYMS_RULE,
    "endpoint_group_gis": GIS_RULE,
    "endpoint_group_tools_check": TOOLS_CHECK_RULE,
    "endpoint_group_tools_jyut2ipa": TOOLS_JYUT2IPA_RULE,
    "endpoint_group_tools_merge": TOOLS_MERGE_RULE,
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
    "/api/tools/praat/jobs",
    "/sql/query",
    "/api/get_coordinates",
]


class RankingDetail:
    """Individual ranking detail."""

    def __init__(self, rank: Optional[int], value: int, gap_to_prev: Optional[int], first_place_value: int, percentile: float):
        self.rank = rank
        self.value = value
        self.gap_to_prev = gap_to_prev
        self.first_place_value = first_place_value
        self.percentile = percentile


def _esc_sql(s: str) -> str:
    return s.replace("'", "''")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _rule_to_cond(rule: RuleConfig) -> str:
    """Convert a RuleConfig to a SQL CASE-WHEN condition string for conditional aggregation."""
    parts = []
    for path in rule.get("paths", []):
        parts.append("aus.path = '{}'".format(_esc_sql(path)))
    for prefix in rule.get("prefixes", []):
        parts.append("aus.path LIKE '{}%'".format(_esc_sql(prefix)))

    if not parts:
        return "0"

    include = " OR ".join(f"({p})" for p in parts)

    for prefix in rule.get("exclude_prefixes", []):
        include = "({}) AND aus.path NOT LIKE '{}%'".format(include, _esc_sql(prefix))

    return include


def _compute_detail(value: int, rank_raw: int, n: int, first: int, next_higher: Optional[int], min_positive: Optional[int]) -> RankingDetail:
    """Compute RankingDetail from SQL result columns, replicating the original _rank_from_totals logic exactly."""
    if value == 0:
        return RankingDetail(
            rank=n + 1,
            value=0,
            gap_to_prev=min_positive,
            first_place_value=first or 0,
            percentile=0.0,
        )

    gap = None if next_higher is None else next_higher - value

    if n <= 1:
        percentile = 100.0
    elif rank_raw < n:
        percentile = round((n - rank_raw) / (n - 1) * 100, 1)
    else:
        percentile = round(100 / (2 * n - 2), 1)

    return RankingDetail(
        rank=rank_raw,
        value=value,
        gap_to_prev=gap,
        first_place_value=first or 0,
        percentile=percentile,
    )


def _build_leaderboard_sql() -> tuple[str, list[str]]:
    """Build the single-shot leaderboard query. Returns (sql, dim_key_order)."""
    # Collect every dimension: (key, rule_or_single_path, is_single_path)
    dims: list[tuple[str, object, bool]] = []

    for cat_name, rule in CATEGORY_RULES.items():
        dims.append((cat_name, rule, False))

    for grp_name, rule in AGGREGATED_ENDPOINT_RULES.items():
        dims.append((grp_name, rule, False))

    for ep_path in ENDPOINT_PATHS:
        key = f"endpoint_{ep_path.replace('/', '_').replace(':', '_')}"
        dims.append((key, ep_path, True))

    key_order = ["online_time", "total_queries"] + [d[0] for d in dims]
    base_cols = ["total_online_seconds", "total_queries"] + [d[0] for d in dims]

    # --- user_totals CTE: one row per user with every dimension total ---
    dim_selects = []
    for alias, rule_or_path, is_single in dims:
        if is_single:
            cond = "aus.path = '{}'".format(_esc_sql(rule_or_path))
        else:
            cond = _rule_to_cond(rule_or_path)
        dim_selects.append(f'COALESCE(SUM(CASE WHEN {cond} THEN aus.count ELSE 0 END), 0) AS {_quote_ident(alias)}')

    # --- ranked CTE: attach window-function stats for every dimension ---
    ranked_exprs = []
    for col in base_cols:
        q = _quote_ident(col)
        ranked_exprs.append(f'RANK() OVER (ORDER BY {q} DESC) AS {_quote_ident(col + "_rank")}')
        ranked_exprs.append(f'MAX({q}) OVER () AS {_quote_ident(col + "_first")}')
        ranked_exprs.append(f'COUNT(*) FILTER (WHERE {q} > 0) OVER () AS {_quote_ident(col + "_n")}')
        ranked_exprs.append(f'MIN({q}) FILTER (WHERE {q} > 0) OVER () AS {_quote_ident(col + "_min_positive")}')

    # --- next-higher subqueries (user-specific, cannot be windowed because of tie-skipping) ---
    next_exprs = []
    for col in base_cols:
        q = _quote_ident(col)
        next_exprs.append(
            f'(SELECT MIN({q}) FROM user_totals WHERE {q} > r.{q}) AS {_quote_ident(col + "_next")}'
        )

    sql = (
        "WITH user_totals AS (\n"
        "    SELECT u.id AS user_id, COALESCE(u.total_online_seconds, 0) AS total_online_seconds,\n"
        "        COALESCE(SUM(aus.count), 0) AS total_queries"
        + (",\n        " + ",\n        ".join(dim_selects) if dim_selects else "")
        + "\n    FROM users u\n"
        "    LEFT JOIN api_usage_summary aus ON u.id = aus.user_id\n"
        "    GROUP BY u.id\n"
        "),\n"
        "ranked AS (\n"
        "    SELECT *,\n        "
        + ",\n        ".join(ranked_exprs)
        + "\n    FROM user_totals\n"
        "),\n"
        "total_stats AS (\n"
        "    SELECT COUNT(*) FILTER (WHERE total_online_seconds > 0) AS total_users\n"
        "    FROM user_totals\n"
        ")\n"
        "SELECT r.*, ts.total_users"
        + (",\n    " + ",\n    ".join(next_exprs) if next_exprs else "")
        + "\nFROM ranked r\n"
        "CROSS JOIN total_stats ts\n"
        "WHERE r.user_id = :user_id"
    )

    return sql, key_order


def get_user_leaderboard(db: Session, user_id: int) -> Dict[str, Dict]:
    """
    Calculate all rankings for a user in a single SQL round-trip.

    Computes:
    - 1 online time ranking
    - 1 total queries ranking
    - 8 category rankings
    - 15 grouped endpoint rankings
    - 16 individual endpoint rankings
    """
    sql, key_order = _build_leaderboard_sql()
    row = db.execute(text(sql), {"user_id": user_id}).fetchone()

    if row is None:
        return {"rankings": {}, "total_users": 0}

    rm = dict(row._mapping)
    total_users = int(rm.get("total_users") or 0)

    rankings_dict = {}
    for key in key_order:
        value = int(rm.get(key) or 0)
        rank_raw = int(rm.get(f"{key}_rank") or 0)
        n = int(rm.get(f"{key}_n") or 0)
        first = int(rm.get(f"{key}_first") or 0)
        next_higher = rm.get(f"{key}_next")
        next_higher = int(next_higher) if next_higher is not None else None
        min_positive = rm.get(f"{key}_min_positive")
        min_positive = int(min_positive) if min_positive is not None else None

        detail = _compute_detail(value, rank_raw, n, first, next_higher, min_positive)
        rankings_dict[key] = {
            "rank": detail.rank,
            "value": detail.value,
            "gap_to_prev": detail.gap_to_prev,
            "first_place_value": detail.first_place_value,
            "percentile": detail.percentile,
        }

    return {
        "rankings": rankings_dict,
        "total_users": total_users,
    }
