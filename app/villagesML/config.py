"""
API配置文件
Configuration file for the Villages Analysis API
"""
import os

# 数据库路径常量 - 使用项目统一路径管理
# Database path constant - using project's centralized path management
from app.common.path import GD_VILLAGE_DB_PATH
DB_PATH = os.getenv("VILLAGES_DB_PATH", GD_VILLAGE_DB_PATH)

# 查询策略配置
# Query policy configuration
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000
DEFAULT_RUN_ID = "freq_final_001"  # 默认分析运行ID（字符频率）
DEFAULT_SEMANTIC_RUN_ID = "semantic_001"  # 语义分析默认run_id
DEFAULT_CLUSTERING_RUN_ID = "cluster_001"  # 聚类分析默认run_id

# API配置
# API configuration
API_TITLE = "广东省自然村分析系统 API"
API_DESCRIPTION = """
Guangdong Province Natural Village Analysis System API

提供285K+村庄的全面分析结果查询接口:
- 字符频率与倾向性分析
- N-gram模式分析
- 语义类别与共现分析
- 空间聚类与热点分析
- 区域聚类画像
- 村庄搜索与过滤

所有重计算已离线完成，API仅提供轻量级查询服务。
"""
API_VERSION = "1.0.0"

# 查询超时配置 (秒)
# Query timeout configuration (seconds)
QUERY_TIMEOUT = 30

# 缓存配置 (可选)
# Cache configuration (optional)
ENABLE_CACHE = False
CACHE_TTL = 3600  # 1 hour

# 计算模块配置
# Compute module configuration
COMPUTE_TIMEOUT = 5  # 单次计算超时（秒）
COMPUTE_SCAN_TIMEOUT = 15  # 参数扫描超时（秒）
COMPUTE_CACHE_SIZE = 100  # 缓存条目数
COMPUTE_CACHE_TTL = 3600  # 缓存过期时间（秒）


def get_db_path() -> str:
    """
    获取数据库路径

    Returns:
        数据库文件路径
    """
    return DB_PATH
