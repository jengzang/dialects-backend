"""
Geographic Distribution Analysis Module

Analyzes user geographic distribution using GeoLite2 database.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
from sqlalchemy import func
from sqlalchemy.orm import Session
import geoip2.database
import os

from app.auth.models import ApiUsageLog


# GeoLite2 database paths
GEOIP_CITY_DB = "data/dependency/GeoLite2-City.mmdb"
GEOIP_COUNTRY_DB = "data/dependency/GeoLite2-Country.mmdb"


def get_geo_reader(level: str = "country"):
    """Get GeoIP2 reader for specified level."""
    db_path = GEOIP_COUNTRY_DB if level == "country" else GEOIP_CITY_DB

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"GeoLite2 database not found: {db_path}")

    return geoip2.database.Reader(db_path)


def get_geo_distribution(
    db: Session,
    level: str = "country"
) -> dict:
    """
    Analyze geographic distribution of users.

    Args:
        db: Database session
        level: 'country' or 'city'

    Returns:
        Dictionary with geographic distribution
    """
    # Get logs from last 7 days
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    logs = db.query(
        ApiUsageLog.ip,
        ApiUsageLog.user_id
    ).filter(
        ApiUsageLog.called_at >= seven_days_ago,
        ApiUsageLog.ip.isnot(None)
    ).all()

    if not logs:
        return {
            "level": level,
            "distribution": []
        }

    # Initialize GeoIP reader
    try:
        reader = get_geo_reader(level)
    except FileNotFoundError as e:
        return {
            "level": level,
            "distribution": [],
            "error": str(e)
        }

    # Analyze IPs
    location_data: Dict[str, dict] = {}
    user_locations: Dict[int, str] = {}  # Track unique users per location

    for log in logs:
        ip = log.ip
        user_id = log.user_id

        try:
            if level == "country":
                response = reader.country(ip)
                location = response.country.names.get('zh-CN') or response.country.names.get('en', 'Unknown')
            else:  # city
                response = reader.city(ip)
                country = response.country.names.get('zh-CN') or response.country.names.get('en', 'Unknown')
                city = response.city.names.get('zh-CN') or response.city.names.get('en', '')
                location = f"{country} - {city}" if city else country

            # Track location data
            if location not in location_data:
                location_data[location] = {
                    "location": location,
                    "call_count": 0,
                    "users": set()
                }

            location_data[location]["call_count"] += 1
            if user_id:
                location_data[location]["users"].add(user_id)

        except (geoip2.errors.AddressNotFoundError, ValueError):
            # IP not found in database or invalid IP
            continue

    reader.close()

    # Calculate distribution
    total_calls = sum(data["call_count"] for data in location_data.values())
    distribution = []

    for location, data in location_data.items():
        percentage = (data["call_count"] / total_calls * 100) if total_calls > 0 else 0
        distribution.append({
            "location": location,
            "user_count": len(data["users"]),
            "call_count": data["call_count"],
            "percentage": round(percentage, 2)
        })

    # Sort by call count
    distribution.sort(key=lambda x: x["call_count"], reverse=True)

    return {
        "level": level,
        "distribution": distribution,
        "total_locations": len(distribution)
    }
