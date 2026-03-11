"""
User Growth Statistics Module

Analyzes user growth trends over time.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.service.auth.models import User


def get_user_growth(
    db: Session,
    months: int = 12
) -> dict:
    """
    Analyze user growth statistics.

    Args:
        db: Database session
        months: Number of recent months to analyze

    Returns:
        Dictionary with monthly growth statistics
    """
    # Calculate start date
    now = datetime.utcnow()
    start_date = now - timedelta(days=months * 30)

    # Get all users with registration date
    users = db.query(
        User.id,
        User.created_at
    ).filter(
        User.created_at.isnot(None)
    ).order_by(User.created_at).all()

    if not users:
        return {
            "monthly_growth": [],
            "summary": {
                "total_users": 0,
                "avg_monthly_growth": 0
            }
        }

    # Group by month
    monthly_data = {}
    cumulative_count = 0

    for user in users:
        if user.created_at:
            month_key = user.created_at.strftime("%Y-%m")

            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    "month": month_key,
                    "new_users": 0,
                    "cumulative_users": 0
                }

            monthly_data[month_key]["new_users"] += 1

    # Calculate cumulative and growth rate
    sorted_months = sorted(monthly_data.keys())
    monthly_growth = []
    prev_cumulative = 0

    for month in sorted_months:
        data = monthly_data[month]
        cumulative_count += data["new_users"]
        data["cumulative_users"] = cumulative_count

        # Calculate growth rate
        if prev_cumulative > 0:
            growth_rate = ((cumulative_count - prev_cumulative) / prev_cumulative) * 100
        else:
            growth_rate = 0

        data["growth_rate"] = round(growth_rate, 2)
        prev_cumulative = cumulative_count

        # Only include recent months
        month_date = datetime.strptime(month, "%Y-%m")
        if month_date >= start_date:
            monthly_growth.append(data)

    # Calculate average monthly growth
    if len(monthly_growth) > 1:
        growth_rates = [m["growth_rate"] for m in monthly_growth if m["growth_rate"] > 0]
        avg_monthly_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0
    else:
        avg_monthly_growth = 0

    return {
        "monthly_growth": monthly_growth,
        "summary": {
            "total_users": cumulative_count,
            "avg_monthly_growth": round(avg_monthly_growth, 2),
            "months_analyzed": len(monthly_growth)
        }
    }
