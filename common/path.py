
# 計算專案根目錄路徑
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# HTML_PATH = os.path.join(BASE_DIR, "index.html")
# JS_PATH = os.path.join(BASE_DIR, "app", "js")
# CSS_PATH = os.path.join(BASE_DIR, "app", "css")

# ============ 路徑 =================

# database路徑依賴
QUERY_DB_PATH = os.path.join(BASE_DIR, "data", "query_dialects.db")
QUERY_DB_ADMIN = os.path.join(BASE_DIR, "data", "query_admin.db")
QUERY_DB_USER = os.path.join(BASE_DIR, "data", "query_user.db")

DIALECTS_DB_PATH = os.path.join(BASE_DIR, "data", "dialects_all.db")
DIALECTS_DB_ADMIN = os.path.join(BASE_DIR, "data", "dialects_admin.db")
DIALECTS_DB_USER = os.path.join(BASE_DIR, "data", "dialects_user.db")

CHARACTERS_DB_PATH = os.path.join(BASE_DIR, "data", "characters.db")
SUPPLE_DB_PATH = os.path.join(BASE_DIR, "data", "supplements.db")
SUPPLE_DB_URL = f"sqlite:///{SUPPLE_DB_PATH}"
# QUERY_DB_PATH = "C:/Users/joengzaang/PycharmProjects/process_phonology/data/dialects_query.db"
# DIALECTS_DB_PATH = "C:/Users/joengzaang/PycharmProjects/process_phonology/data/dialects_all.db"
# CHARACTERS_DB_PATH = "C:/Users/joengzaang/PycharmProjects/process_phonology/data/characters.db"

YC_SPOKEN_DB_PATH = os.path.join(BASE_DIR, "data", "yc_spoken.db")
GD_VILLAGE_DB_PATH = os.path.join(BASE_DIR, "data", "villages.db")
YUBAO_DB_PATH = os.path.join(BASE_DIR, "data", "yubao.db")

# 字表寫入SQL路徑依賴
APPEND_PATH = os.path.join(BASE_DIR, "make", "data", "dependency", "jengzang補充.xlsx")
HAN_PATH = os.path.join(BASE_DIR, "make", "data", "dependency", "漢字音典字表檔案（長期更新）.xlsx")
HAN_CSV_PATH = os.path.join(BASE_DIR, "make", "data", "dependency", "漢字音典字表檔案（長期更新）-檔案.csv")  # 暫未使用
PHO_TABLE_PATH = os.path.join(BASE_DIR, "make", "data", "dependency", "聲韻.xlsx")
RAW_DATA_DIR = os.path.join(BASE_DIR, "make", "data", "raw")
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "make", "data", "processed")
YINDIAN_DATA_DIR = os.path.join(BASE_DIR, "make", "data", "yindian")
# APPEND_PATH = "C:/Users/joengzaang/PycharmProjects/process_phonology/data/dependency/Append_files.xlsx"
# HAN_PATH = "C:/Users/joengzaang/PycharmProjects/process_phonology/data/dependency/漢字音典字表檔案（長期更新）.xlsx"
# PHO_TABLE_PATH = "C:/Users/joengzaang/PycharmProjects/process_phonology/data/dependency/聲韻.xlsx"

# 通用路徑依賴
ZHENGZI_PATH = os.path.join(BASE_DIR, "data", "dependency", "正字.tsv")
MULCODECHAR_PATH = os.path.join(BASE_DIR, "data", "dependency", "mulcodechar.dt")
# ZHENGZI_PATH = "C:/Users/joengzaang/PycharmProjects/process_phonology/data/dependency/正字.tsv"
# MULCODECHAR_PATH = "C:/Users/joengzaang/PycharmProjects/process_phonology/data/dependency/mulcodechar.dt"

# api_logs路徑依賴
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)  # [OK] 主动创建 logs 目录
KEYWORD_LOG_FILE = os.path.join(log_dir, "api_keywords_log.txt")
SUMMARY_FILE = os.path.join(log_dir, "api_keywords_summary.txt")
API_USAGE_FILE = os.path.join(log_dir, "api_usage_stats.txt")
API_DETAILED_FILE = os.path.join(log_dir, "api_detailed_stats.txt")
API_DETAILED_JSON = os.path.join(log_dir, "api_detailed_stats.json")

# 字表處理路徑依賴
MISSING_DATA_LOG = os.path.join(BASE_DIR, "logs", "缺資料.txt")
WRITE_INFO_LOG = os.path.join(BASE_DIR, "logs", "write.txt")
WRITE_ERROR_LOG = os.path.join(BASE_DIR, "logs", "write_error.txt")

# ========== 登錄系統 =============
USER_DATABASE_PATH = os.path.join(BASE_DIR, "data", "auth.db")
USER_DATABASE_URL = f"sqlite:///{USER_DATABASE_PATH}"

# ========== 日志系統 =============
LOGS_DATABASE_PATH = os.path.join(BASE_DIR, "data", "logs.db")
LOGS_DATABASE_URL = f"sqlite:///{LOGS_DATABASE_PATH}"

# ==========數據庫系統===========
DB_MAPPING = {
    "spoken": YC_SPOKEN_DB_PATH,
    "village": GD_VILLAGE_DB_PATH,
    "chars": CHARACTERS_DB_PATH,
    "query": QUERY_DB_USER,
    "query_admin": QUERY_DB_ADMIN,
    "dialects": DIALECTS_DB_USER,
    "dialects_admin": DIALECTS_DB_ADMIN,
    "yubao": YUBAO_DB_PATH,
    "logs": LOGS_DATABASE_PATH,
    "supple": SUPPLE_DB_PATH,
    "auth": USER_DATABASE_PATH
}
# 管理员专属数据库
ADMIN_ONLY_DBS = {"query_admin", "dialects_admin", "logs", "supple", "auth"}