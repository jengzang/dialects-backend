"""
Cluster tool configuration constants.
"""

from __future__ import annotations

FEATURE_COLUMN_MAP = {
    "initial": "聲母",
    "final": "韻母",
    "tone": "聲調",
}

TONE_SLOT_COLUMNS = [
    "T1陰平",
    "T2陽平",
    "T3陰上",
    "T4陽上",
    "T5陰去",
    "T6陽去",
    "T7陰入",
    "T8陽入",
    "T9其他調",
    "T10輕聲",
]

DEFAULT_FILTERED_YINDIAN_REGIONS = {
    "域外方音",
    "歷史音",
    "現代標準漢語",
    "民語漢字音",
}

DEFAULT_PHONEME_MODE = "intra_group"
DEFAULT_ANCHOR_WEIGHT = 0.15
DEFAULT_SHARED_IDENTITY_WEIGHT = 0.20
INTRA_CORR_WEIGHT = 0.85
INTRA_STRUCT_WEIGHT = 0.15
TASK_TOOL_NAME = "cluster"
CACHE_TTL_SECONDS = 600
RESULT_CACHE_TTL_SECONDS = 24 * 60 * 60
INFLIGHT_CACHE_TTL_SECONDS = 20 * 60
LOADER_CACHE_TTL_SECONDS = 30 * 60
LOADER_CACHE_MAX_LOCATIONS = 500
LOADER_CACHE_MAX_CHARS = 5000
LOADER_CACHE_MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
DIST_EPSILON = 1e-12
