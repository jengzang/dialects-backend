"""
User Behavior Analytics Module

This module provides comprehensive user behavior analysis capabilities:
- User segmentation and activity analysis
- RFM (Recency, Frequency, Monetary) value analysis
- Anomaly detection
- API diversity and preference analysis
- Growth statistics and dashboard
- Performance and trend analysis
- Geographic and device distribution
- Data export functionality
"""

from .segmentation import get_user_segments
from .rfm import get_rfm_analysis
from .anomaly import detect_anomalies
from .diversity import get_api_diversity
from .preferences import get_user_preferences
from .growth import get_user_growth
from .dashboard import get_dashboard_data
from .trends import get_recent_trends
from .performance import get_api_performance
from .geo import get_geo_distribution
from .devices import get_device_distribution
from .export import export_data

__all__ = [
    "get_user_segments",
    "get_rfm_analysis",
    "detect_anomalies",
    "get_api_diversity",
    "get_user_preferences",
    "get_user_growth",
    "get_dashboard_data",
    "get_recent_trends",
    "get_api_performance",
    "get_geo_distribution",
    "get_device_distribution",
    "export_data",
]
