# schemas/__init__.py
"""
Pydantic schemas for request/response validation

重组后的目录结构：
- auth/: 认证相关 (user, session)
- admin/: 管理后台 (users, permissions, submissions, analytics)
- user/: 用户功能 (submissions, profile)
- core/: 核心业务 (phonology, compare, query, coordinates)
- common/: 通用schemas (pagination, response)
"""

# 核心业务 schemas (保持向后兼容)
from .core.coordinates import CoordinatesQuery
from .core.phonology import (
    AnalysisPayload,
    PhonologyClassificationMatrixRequest,
    PhonologyMatrixRequest,
    FeatureStatsRequest
)
from .user.submissions import FormData
from .core.query import QueryParams, FeatureQueryParams

__all__ = [
    "AnalysisPayload",
    "PhonologyClassificationMatrixRequest",
    "PhonologyMatrixRequest",
    "FeatureStatsRequest",
    "FormData",
    "QueryParams",
    "FeatureQueryParams",
    "CoordinatesQuery"
]
