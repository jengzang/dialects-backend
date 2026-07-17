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

# === Auth Cookie 配置（Web 端 HttpOnly Cookie） ===
# Cookie 名称：生产环境建议 __Host-access_token，开发环境用 access_token
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "access_token")
# 生产环境必须为 true；开发环境 (http://localhost) 可设为 false
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() in ("1", "true", "yes", "on")
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax")  # lax / strict / none
AUTH_COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN", "") or None  # 空字符串 → 不设 Domain（配合 __Host- 前缀）

# Refresh Token Cookie（Web 端）
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")
REFRESH_COOKIE_SECURE = os.getenv("REFRESH_COOKIE_SECURE", str(AUTH_COOKIE_SECURE)).lower() in ("1", "true", "yes", "on")
REFRESH_COOKIE_SAMESITE = os.getenv("REFRESH_COOKIE_SAMESITE", AUTH_COOKIE_SAMESITE)

# === CSRF 防护 ===
CSRF_ENABLED = os.getenv("CSRF_ENABLED", "true").lower() in ("1", "true", "yes", "on")
# 可信 Origin 列表（逗号分隔），用于校验 Cookie 认证的写请求
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = ["https://dialects.yzup.top", "https://yzup.top"]

# Access Token 过期秒数（cookie max_age 用，与 ACCESS_TOKEN_EXPIRE_MINUTES 对应）
ACCESS_TOKEN_EXPIRE_SECONDS = ACCESS_TOKEN_EXPIRE_MINUTES * 60
# Refresh Token 过期秒数（cookie max_age 用）
REFRESH_TOKEN_EXPIRE_SECONDS = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
