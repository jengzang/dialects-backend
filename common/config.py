import os
import socket

# ============ 路徑 =================
# 計算專案根目錄路徑
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

QUERY_DB_ADMIN = os.path.join(BASE_DIR, "data", "query_admin.db")
QUERY_DB_USER = os.path.join(BASE_DIR, "data", "query_user.db")

DIALECTS_DB_ADMIN = os.path.join(BASE_DIR, "data", "dialects_admin.db")
DIALECTS_DB_USER = os.path.join(BASE_DIR, "data", "dialects_user.db")

CHARACTERS_DB_PATH = os.path.join(BASE_DIR, "data", "characters.db")
SUPPLE_DB_PATH = os.path.join(BASE_DIR, "data", "supplements.db")
SUPPLE_DB_URL = f"sqlite:///{SUPPLE_DB_PATH}"


# 通用路徑依賴
ZHENGZI_PATH = os.path.join(BASE_DIR, "data", "dependency", "正字.tsv")
MULCODECHAR_PATH = os.path.join(BASE_DIR, "data", "dependency", "mulcodechar.dt")

# api_logs路徑依賴
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)  # ✅ 主动创建 logs 目录
KEYWORD_LOG_FILE = os.path.join(log_dir, "api_keywords_log.txt")
SUMMARY_FILE = os.path.join(log_dir, "api_keywords_summary.txt")
API_USAGE_FILE = os.path.join(log_dir, "api_usage_stats.txt")
API_DETAILED_FILE = os.path.join(log_dir, "api_detailed_stats.txt")
API_DETAILED_JSON = os.path.join(log_dir, "api_detailed_stats.json")

# 字表處理路徑依賴
MISSING_DATA_LOG = os.path.join(BASE_DIR, "logs", "缺資料.txt")
WRITE_INFO_LOG = os.path.join(BASE_DIR, "logs", "write.txt")
WRITE_ERROR_LOG = os.path.join(BASE_DIR, "logs", "write_error.txt")

# 是否刪除一星期前的api記錄
CLEAR_WEEK = False
# 只记录路径中包含以下词的 API
RECORD_API = [
    "phonology",  # 可以匹配 "/api/phonology"
    "get_coordinates",  # 可以匹配 "/api/get_coordinates"
    "search_tones",  # 可以匹配 "/api/search_tones/"
    "search_chars",  # 可以匹配 "/api/search_chars/"
    "submit_form",
    "delete_form"
]

# ========== 登錄系統 =============
USER_DATABASE_PATH = os.path.join(BASE_DIR, "data", "auth.db")
USER_DATABASE_URL = f"sqlite:///{USER_DATABASE_PATH}"

SECRET_KEY = "your-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10000
ISSUER = "dialects_api"  # 可自定義
AUDIENCE = "dialects_web"  # 可自定義

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
MAX_USER_USAGE_PER_HOUR = 1000  # 1000秒
MAX_IP_USAGE_PER_HOUR = 500

# 用戶能接收的最大json包
MAX_ANONYMOUS_SIZE = 1024 * 1024  # 1MB for anonymous users
MAX_USER_SIZE = 6 * 1024 * 1024   # 6MB for authenticated users

# =============== 配置 =======================
# banner配置
APP_NAME = "Dialect Compare Tool — FastAPI Backend"
AUTHOR = "不羈 (JengZang)"
VERSION = "1.0.2"
DATE_STR = "2025-09-01"

# --------運行方式------------
_RUN_TYPE = 'MINE'  # MINE/EXE/WEB
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
