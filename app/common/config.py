import os
import socket

# --------運行方式------------
# _RUN_TYPE = 'WEB'  # MINE/EXE/WEB
_RUN_TYPE = os.getenv('_RUN_TYPE', 'WEB')  # 默认为 'WEB'

SQL_QUERY_MAX_PAGE = 50
SQL_TREE_FULL_MAX_ROWS = 5000
SQL_TREE_FULL_PRECHECK_COUNT_THRESHOLD = 5000
SQL_TREE_LAZY_ROOT_MAX_CHILDREN = 500

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
