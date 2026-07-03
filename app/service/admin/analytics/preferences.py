"""
User Preferences Analysis Module

Analyzes user preferences based on API usage patterns.
Returns detailed data for frontend to generate labels.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.service.auth.database.models import User, ApiUsageSummary


# API category mapping
# 与 leaderboard_service.CATEGORY_RULES 保持一致
API_CATEGORIES = {
    "音韵查询": [
        "/api/ZhongGu",
        "/api/YinWei",
        "/api/phonology",
        "/api/charlist",
        "/api/feature_stats",
        "/api/compare/ZhongGu",
    ],
    "字调查询": [
        "/api/search_chars/",
        "/api/search_tones/",
        "/api/compare/chars",
        "/api/compare/tones",
        "/api/yubao/",
    ],
    "音系分析": [
        "/api/phonology_matrix",
        "/api/phonology_classification_matrix",
        "/api/feature_counts",
        "/api/pho_pie_by_value",
        "/api/pho_pie_by_status",
    ],
    "工具使用": [
        "/api/tools/check/analyze",
        "/api/tools/jyut2ipa/process",
        "/api/tools/merge/execute",
        "/api/tools/praat/jobs",
    ],
    "其他查询": [
        "/sql/query",
        "/sql/tree/full",
        "/sql/tree/lazy",
        "/api/get_coordinates",
        "/api/villages/",
        "/api/locations/",
    ],
}

# 排除规则：匹配到这些模式的路径不计入对应分类
CATEGORY_EXCLUDES = {
    "其他查询": ["/api/villages/admin/"],
}


def categorize_api(path: str) -> str:
    """Categorize API path into a category."""
    for category, paths in API_CATEGORIES.items():
        for api_path in paths:
            if api_path in path:
                # 检查排除规则
                excludes = CATEGORY_EXCLUDES.get(category, [])
                if any(ex in path for ex in excludes):
                    continue
                return category
    return "其他"


def get_user_preferences(
    db: Session,
    user_ids: Optional[List[int]] = None
) -> dict:
    """
    Analyze user preferences based on API usage.

    Args:
        db: Database session
        user_ids: Optional list of user IDs to analyze (if None, analyze all)

    Returns:
        Dictionary with user preference data
    """
    # Build query
    query = db.query(
        User.id,
        User.username,
        ApiUsageSummary.path,
        ApiUsageSummary.count,
        ApiUsageSummary.total_upload,
        ApiUsageSummary.total_download
    ).join(
        ApiUsageSummary, User.id == ApiUsageSummary.user_id
    )

    if user_ids:
        query = query.filter(User.id.in_(user_ids))

    usage_data = query.all()

    # Group by user
    user_data = {}
    for row in usage_data:
        user_id = row.id
        if user_id not in user_data:
            user_data[user_id] = {
                "user_id": user_id,
                "username": row.username,
                "apis": [],
                "total_calls": 0,
                "total_upload": 0,
                "total_download": 0,
                "categories": {}
            }

        calls = int(row.count)
        upload = float(row.total_upload)
        download = float(row.total_download)

        user_data[user_id]["apis"].append({
            "path": row.path,
            "calls": calls
        })
        user_data[user_id]["total_calls"] += calls
        user_data[user_id]["total_upload"] += upload
        user_data[user_id]["total_download"] += download

        # Categorize
        category = categorize_api(row.path)
        if category not in user_data[user_id]["categories"]:
            user_data[user_id]["categories"][category] = 0
        user_data[user_id]["categories"][category] += calls

    # Process each user
    users = []
    for user_id, data in user_data.items():
        total_calls = data["total_calls"]
        total_traffic = data["total_upload"] + data["total_download"]

        # Calculate category distribution (percentage)
        category_distribution = {}
        for category, calls in data["categories"].items():
            percentage = (calls / total_calls * 100) if total_calls > 0 else 0
            category_distribution[category] = round(percentage, 2)

        # Calculate API diversity
        api_diversity = len(data["apis"])
        diversity_score = api_diversity / total_calls if total_calls > 0 else 0

        # Calculate traffic pattern
        upload_ratio = data["total_upload"] / total_traffic if total_traffic > 0 else 0
        download_ratio = data["total_download"] / total_traffic if total_traffic > 0 else 0

        # Get top APIs
        top_apis = sorted(data["apis"], key=lambda x: x["calls"], reverse=True)[:5]
        for api in top_apis:
            api["percentage"] = round(api["calls"] / total_calls * 100, 2) if total_calls > 0 else 0

        users.append({
            "user_id": user_id,
            "username": data["username"],
            "category_distribution": category_distribution,
            "total_calls": total_calls,
            "api_diversity": api_diversity,
            "diversity_score": round(diversity_score, 4),
            "traffic_pattern": {
                "upload_ratio": round(upload_ratio, 2),
                "download_ratio": round(download_ratio, 2),
                "total_traffic_kb": round(total_traffic, 2)
            },
            "top_apis": top_apis
        })

    return {"users": users}
