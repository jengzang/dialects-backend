"""
Device Distribution Analysis Module

Analyzes user device types, browsers, and operating systems.
"""

from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session
from user_agents import parse

from app.service.auth.database.models import ApiUsageLog


def get_device_distribution(db: Session) -> dict:
    """
    Analyze device distribution from user agents.

    Args:
        db: Database session

    Returns:
        Dictionary with device distribution data
    """
    # Get logs from last 7 days
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    logs = db.query(
        ApiUsageLog.user_agent,
        ApiUsageLog.user_id
    ).filter(
        ApiUsageLog.called_at >= seven_days_ago,
        ApiUsageLog.user_agent.isnot(None)
    ).all()

    if not logs:
        return {
            "device_types": [],
            "browsers": [],
            "os": []
        }

    # Initialize counters
    device_types: Dict[str, set] = {}
    browsers: Dict[str, set] = {}
    operating_systems: Dict[str, set] = {}

    # Parse user agents
    for log in logs:
        user_agent_string = log.user_agent
        user_id = log.user_id

        try:
            user_agent = parse(user_agent_string)

            # Device type
            if user_agent.is_mobile:
                device_type = "mobile"
            elif user_agent.is_tablet:
                device_type = "tablet"
            elif user_agent.is_pc:
                device_type = "desktop"
            else:
                device_type = "other"

            if device_type not in device_types:
                device_types[device_type] = set()
            if user_id:
                device_types[device_type].add(user_id)

            # Browser
            browser = user_agent.browser.family
            if browser:
                if browser not in browsers:
                    browsers[browser] = set()
                if user_id:
                    browsers[browser].add(user_id)

            # Operating System
            os_name = user_agent.os.family
            if os_name:
                if os_name not in operating_systems:
                    operating_systems[os_name] = set()
                if user_id:
                    operating_systems[os_name].add(user_id)

        except Exception:
            # Failed to parse user agent
            continue

    # Calculate distributions
    total_users = len(set(log.user_id for log in logs if log.user_id))

    def calculate_distribution(data_dict: Dict[str, set]) -> List[dict]:
        """Helper to calculate distribution percentages."""
        result = []
        for name, users in data_dict.items():
            count = len(users)
            percentage = (count / total_users * 100) if total_users > 0 else 0
            result.append({
                "name": name,
                "count": count,
                "percentage": round(percentage, 2)
            })
        # Sort by count
        result.sort(key=lambda x: x["count"], reverse=True)
        return result

    return {
        "device_types": calculate_distribution(device_types),
        "browsers": calculate_distribution(browsers),
        "os": calculate_distribution(operating_systems),
        "total_users": total_users
    }
