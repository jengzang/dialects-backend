import os
import socket

from common.api_config import API_ROUTE_CONFIG

# --------運行方式------------
# _RUN_TYPE = 'WEB'  # MINE/EXE/WEB
_RUN_TYPE = os.getenv('_RUN_TYPE', 'WEB')  # 默认为 'WEB'

# =========JWT==============
SECRET_KEY = "super-secret-key"
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

# 一小時內用戶使用api時長
MAX_USER_USAGE_PER_HOUR = 2000  # 1000秒
MAX_IP_USAGE_PER_HOUR = 300

# 用戶能接收的最大json包
MAX_ANONYMOUS_SIZE = 1024 * 1024  # 1MB for anonymous users
MAX_USER_SIZE = 6 * 1024 * 1024  # 6MB for authenticated users
# 压缩阈值
SIZE_THRESHOLD = 10 * 1024  # 10KB
# 每20条日志写入一次
BATCH_SIZE = 20
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

