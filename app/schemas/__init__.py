# schemas/__init__.py
from .coordinates import CoordinatesQuery
from .phonology import AnalysisPayload, PhonologyClassificationMatrixRequest, PhonologyMatrixRequest
from .form import FormData
from .query_custom import QueryParams, FeatureQueryParams

__all__ = [
    "AnalysisPayload",
    "PhonologyClassificationMatrixRequest",
    "PhonologyMatrixRequest",
    "FormData",
    "QueryParams",
    "FeatureQueryParams",
    "CoordinatesQuery"
]
