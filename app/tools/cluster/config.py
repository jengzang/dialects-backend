"""
cluster 工具的集中配置。

这里统一维护整个聚类链路都会依赖的常量，包括：
- 维度名到数据库列名的映射；
- 默认过滤的特殊地点类型；
- 三种 phoneme_mode 的权重参数；
- 结果缓存、inflight、loader 缓存的 TTL 与写入门槛；
- 数值计算时用于防止除零和 log(0) 的极小量。
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

# 默认会过滤一些不适合直接和普通方言点一起聚类的特殊点。
DEFAULT_FILTERED_YINDIAN_REGIONS = {
    "域外方音",
    "歷史音",
    "現代標準漢語",
    "民語漢字音",
}

# 当前默认的音系距离模式是纯组内比较。
DEFAULT_PHONEME_MODE = "intra_group"
# anchored_inventory 模式中，库存锚点距离占总距离的 15%。
DEFAULT_ANCHOR_WEIGHT = 0.15
# shared_request_identity 模式中，共享身份距离占总距离的 20%。
DEFAULT_SHARED_IDENTITY_WEIGHT = 0.20
# 组内距离又细分为“对应关系稳定性”和“同音结构差异”两部分。
INTRA_CORR_WEIGHT = 0.85
INTRA_STRUCT_WEIGHT = 0.15
TASK_TOOL_NAME = "cluster"
CACHE_TTL_SECONDS = 600
RESULT_CACHE_TTL_SECONDS = 24 * 60 * 60
INFLIGHT_CACHE_TTL_SECONDS = 20 * 60
# loader 只缓存中小请求，避免把全量 dialect_data 塞入 Redis。
LOADER_CACHE_TTL_SECONDS = 30 * 60
LOADER_CACHE_MAX_LOCATIONS = 500
LOADER_CACHE_MAX_CHARS = 5000
LOADER_CACHE_MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
STAGED_ARTIFACT_ROOT_DIRNAME = "_artifacts"
STAGED_PREVIEW_TTL_SECONDS = 5 * 60 * 60
STAGED_PREPARE_TTL_SECONDS = 60 * 60
STAGED_DISTANCE_TTL_SECONDS = 60 * 60
STAGED_RESULT_TTL_SECONDS = 2 * 60 * 60
# 数值保护项，避免出现 log(0) 与除零。
DIST_EPSILON = 1e-12
