"""
认证系统配置
包含：Session管理、Token管理、安全阈值等
"""
import os

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

# =========JWT==============
# SECRET_KEY管理（延迟加载）
_SECRET_KEY_CACHE = None
_ENV_SECRET_KEY = os.getenv("SECRET_KEY", "").strip()

def get_secret_key() -> str:
    """获取SECRET_KEY（延迟加载）"""
    global _SECRET_KEY_CACHE

    if _SECRET_KEY_CACHE is not None:
        return _SECRET_KEY_CACHE

    # 尝试从数据库加载
    try:
        from app.service.auth.security.key_manager import get_current_secret_key
        _SECRET_KEY_CACHE = get_current_secret_key()
        print(f"[CONFIG] ✅ Loaded SECRET_KEY from database: {_SECRET_KEY_CACHE[:20]}...")
        return _SECRET_KEY_CACHE
    except Exception as e:
        if _ENV_SECRET_KEY:
            _SECRET_KEY_CACHE = _ENV_SECRET_KEY
            print("[CONFIG] ⚠️  Using SECRET_KEY from environment fallback")
            return _SECRET_KEY_CACHE

        # Fallback: 使用临时密钥（仅用于初次迁移）
        print(f"[CONFIG] ⚠️  Failed to load SECRET_KEY from database: {e}")
        print("[CONFIG] ⚠️  Using temporary fallback key")
        import secrets
        _SECRET_KEY_CACHE = secrets.token_urlsafe(64)
        return _SECRET_KEY_CACHE

def get_old_secret_keys():
    """获取旧的有效密钥（延迟加载）"""
    try:
        from app.service.auth.security.key_manager import get_all_valid_keys
        current = get_secret_key()
        return [k for k in get_all_valid_keys() if k != current]
    except:
        return []

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Changed from 100000 to 30 minutes for security
REFRESH_TOKEN_EXPIRE_DAYS = 30    # New: 30 days for refresh tokens
MAX_ACTIVE_REFRESH_TOKENS = 10     # New: Limit active devices per user
ISSUER = "dialects_api"  # 可自定義
AUDIENCE = "dialects_web"  # 可自定義

# =============register=========
# 是否要求郵件驗證
REQUIRE_EMAIL_VERIFICATION = False  # 改成 False 就不需要驗證
# 限制註冊頻率
MAX_REGISTRATIONS_PER_IP = 3
REGISTRATION_WINDOW_MINUTES = 10
# 每分鐘最多嘗試登錄
MAX_LOGIN_PER_MINUTE = 10

# 登錄才能用
REQUIRE_LOGIN = False


# 注意：Session表不需要清理（每个用户最多10个session，不会膨胀）

# === 环境变量覆盖（可选）===
MAX_SESSIONS_PER_USER = int(os.getenv("MAX_SESSIONS_PER_USER", MAX_SESSIONS_PER_USER))
MAX_TOKENS_PER_SESSION = int(os.getenv("MAX_TOKENS_PER_SESSION", MAX_TOKENS_PER_SESSION))
SUSPICIOUS_IP_CHANGES = int(os.getenv("SUSPICIOUS_IP_CHANGES", SUSPICIOUS_IP_CHANGES))
SUSPICIOUS_DEVICE_CHANGES = int(os.getenv("SUSPICIOUS_DEVICE_CHANGES", SUSPICIOUS_DEVICE_CHANGES))
