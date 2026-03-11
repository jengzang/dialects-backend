"""
认证系统配置
包含：Session管理、Token管理、安全阈值等
"""

# === Session限制 ===
MAX_SESSIONS_PER_USER = 10  # 每个用户最多同时活跃session数
MAX_TOKENS_PER_SESSION = 20  # 每个session保留的token历史记录数

# === 可疑会话检测阈值 ===
SUSPICIOUS_IP_CHANGES = 10  # IP切换次数超过此值标记为可疑
SUSPICIOUS_DEVICE_CHANGES = 5  # 设备切换次数超过此值标记为可疑
SUSPICIOUS_REFRESH_COUNT = 100  # 24小时内刷新次数超过此值标记为可疑

# === 清理策略 ===
TOKEN_RETENTION_DAYS = 7  # 已撤销的refresh token保留天数（之后永久删除）
IP_HISTORY_LIMIT = 50  # IP历史记录保留数量

# 注意：Session表不需要清理（每个用户最多10个session，不会膨胀）

# === Token配置（从common/config.py导入，保持兼容性）===
from app.common.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
    ALGORITHM
)

# === 环境变量覆盖（可选）===
import os
MAX_SESSIONS_PER_USER = int(os.getenv("MAX_SESSIONS_PER_USER", MAX_SESSIONS_PER_USER))
MAX_TOKENS_PER_SESSION = int(os.getenv("MAX_TOKENS_PER_SESSION", MAX_TOKENS_PER_SESSION))
SUSPICIOUS_IP_CHANGES = int(os.getenv("SUSPICIOUS_IP_CHANGES", SUSPICIOUS_IP_CHANGES))
SUSPICIOUS_DEVICE_CHANGES = int(os.getenv("SUSPICIOUS_DEVICE_CHANGES", SUSPICIOUS_DEVICE_CHANGES))
