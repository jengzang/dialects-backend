import os
import socket

# --------運行方式------------
# _RUN_TYPE = 'WEB'  # MINE/EXE/WEB
_RUN_TYPE = os.getenv('_RUN_TYPE', 'WEB')  # 默认为 'WEB'

# =========JWT==============
# SECRET_KEY管理（延迟加载）
_SECRET_KEY_CACHE = None
_SECRET_KEY_LOADED = False

def get_secret_key() -> str:
    """获取SECRET_KEY（延迟加载）"""
    global _SECRET_KEY_CACHE, _SECRET_KEY_LOADED

    if _SECRET_KEY_CACHE is not None:
        return _SECRET_KEY_CACHE

    # 尝试从数据库加载
    try:
        from app.service.auth.key_manager import get_current_secret_key
        _SECRET_KEY_CACHE = get_current_secret_key()
        _SECRET_KEY_LOADED = True
        print(f"[CONFIG] ✅ Loaded SECRET_KEY from database: {_SECRET_KEY_CACHE[:20]}...")
        return _SECRET_KEY_CACHE
    except Exception as e:
        # Fallback: 使用临时密钥（仅用于初次迁移）
        print(f"[CONFIG] ⚠️  Failed to load SECRET_KEY from database: {e}")
        print("[CONFIG] ⚠️  Using temporary fallback key")
        import secrets
        _SECRET_KEY_CACHE = secrets.token_urlsafe(64)
        _SECRET_KEY_LOADED = False
        return _SECRET_KEY_CACHE

def get_old_secret_keys():
    """获取旧的有效密钥（延迟加载）"""
    try:
        from app.service.auth.key_manager import get_all_valid_keys
        current = get_secret_key()
        return [k for k in get_all_valid_keys() if k != current]
    except:
        return []

# 向后兼容：提供全局变量（但使用时会调用函数）
SECRET_KEY = None  # 将在首次使用时通过 get_secret_key() 加载
OLD_SECRET_KEYS = []  # 将在首次使用时通过 get_old_secret_keys() 加载

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

# 缓存过期时间（例如：1小时）
CACHE_EXPIRATION_TIME = 3600  # 秒


# =============== 配置 =======================
# banner配置
APP_NAME = "Dialect Compare Tool — FastAPI Backend"
AUTHOR = "不羈 (JengZang)"
VERSION = "2.0.1"
DATE_STR = "2026-01-29"


# --------------------------

def get_local_ip():
    """獲取當前主機的內網 IP（非 127.0.0.1）"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 不需要真的發包
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


PORT = 5000
LOCAL_IP = get_local_ip() if _RUN_TYPE == "MINE" else "127.0.0.1"
APP_URL = f"http://{LOCAL_IP}:{PORT}"


# === 自动迁移配置 ===
AUTO_MIGRATE = os.getenv("AUTO_MIGRATE", "true").lower() == "true"
MIGRATION_TIMEOUT = int(os.getenv("MIGRATION_TIMEOUT", "300"))  # 5分钟

# 打印配置（仅在启动时）
if AUTO_MIGRATE:
    print("[CONFIG] 自动迁移: 启用")
else:
    print("[CONFIG] 自动迁移: 禁用（需手动运行迁移）")

