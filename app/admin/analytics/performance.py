"""
API Performance Analysis Module

Analyzes API response time and performance metrics.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
import statistics

from app.auth.models import ApiUsageLog


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate percentile value."""
    if not values:
        return 0
    sorted_values = sorted(values)
    index = int(len(sorted_values) * percentile)
    return sorted_values[min(index, len(sorted_values) - 1)]


def get_api_performance(
    db: Session,
    api_path: Optional[str] = None
) -> dict:
    """
    Analyze API performance metrics.

    Args:
        db: Database session
        api_path: Optional specific API path to analyze

    Returns:
        Dictionary with performance metrics
    """
    # Get logs from last 7 days
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    query = db.query(ApiUsageLog).filter(
        ApiUsageLog.called_at >= seven_days_ago
    )

    if api_path:
        query = query.filter(ApiUsageLog.path == api_path)

    logs = query.all()

    if not logs:
        return {
            "apis": [],
            "summary": {
                "overall_avg": 0,
                "slowest_api": None
            }
        }

    # Group by API path
    api_data = {}
    for log in logs:
        path = log.path
        if path not in api_data:
            api_data[path] = {
                "durations": [],
                "total_calls": 0
            }

        api_data[path]["durations"].append(log.duration)
        api_data[path]["total_calls"] += 1

    # Calculate metrics for each API
    apis = []
    all_durations = []

    for path, data in api_data.items():
        durations = data["durations"]
        all_durations.extend(durations)

        avg_duration = statistics.mean(durations)
        p50 = calculate_percentile(durations, 0.50)
        p95 = calculate_percentile(durations, 0.95)
        p99 = calculate_percentile(durations, 0.99)

        # Calculate slow request ratio (> 1 second)
        slow_requests = sum(1 for d in durations if d > 1.0)
        slow_request_ratio = (slow_requests / len(durations) * 100) if durations else 0

        apis.append({
            "path": path,
            "avg_duration": round(avg_duration, 3),
            "p50": round(p50, 3),
            "p95": round(p95, 3),
            "p99": round(p99, 3),
            "slow_request_ratio": round(slow_request_ratio, 2),
            "total_calls": data["total_calls"]
        })

    # Sort by average duration (slowest first)
    apis.sort(key=lambda x: x["avg_duration"], reverse=True)

    # Calculate overall metrics
    overall_avg = statistics.mean(all_durations) if all_durations else 0
    slowest_api = apis[0]["path"] if apis else None

    return {
        "apis": apis,
        "summary": {
            "overall_avg": round(overall_avg, 3),
            "slowest_api": slowest_api,
            "total_apis": len(apis)
        }
    }
