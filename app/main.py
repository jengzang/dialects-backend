# app/main.py
import os
import threading
import time
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.auth.database import get_db
from app.redis_client import close_redis
from app.routes import setup_routes
from app.logs.service.api_logger import start_api_logger_workers, stop_api_logger_workers, TrafficLoggingMiddleware
from app.logs.service.api_limit_keyword import ApiLoggingMiddleware
from app.auth.service import start_user_activity_writer, stop_user_activity_writer  # [NEW] 用户活动队列
from app.static_utils import ensure_user_data  # 如果你要用它挂载静态资源
from common.config import _RUN_TYPE
from starlette.staticfiles import StaticFiles

# [OK] 导入日志迁移模块
# from app.logs.migrate_from_txt import run_migration
# [OK] 导入定时任务模块
from app.logs.scheduler import start_scheduler, stop_scheduler
# [OK] 导入数据库索引管理模块
from app.sql.index_manager import initialize_all_indexes
# [NEW] 导入数据库连接池管理模块
from app.sql.db_pool import close_all_pools, get_db_pool
from common.path import (
    QUERY_DB_ADMIN, QUERY_DB_USER,
    DIALECTS_DB_ADMIN, DIALECTS_DB_USER,
    CHARACTERS_DB_PATH
)

if _RUN_TYPE == 'EXE':
    # === 周期打印 ===
    print_lock = threading.Lock()
    active_requests = 0
    _printer_started = False


    def _periodic_printer():
        msg = (
            "\n\n##################################\n"
            "歡迎使用  方言比較 - 地理語言學  小工具\n "
            " 開發者：不羈   2026年1月\n"
            "------------------------------------\n"
            "這個窗口不能關！！這是python fastapi後端！！\n"
            "###################################"
        )
        while True:
            time.sleep(200)
            with print_lock:
                if active_requests == 0:
                    print(msg)
                    now = time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{now}] Backend alive [OK]  開發者: 不羈")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _RUN_TYPE == 'EXE':
        global _printer_started
        if not _printer_started:
            _printer_started = True
            t = threading.Thread(target=_periodic_printer, daemon=True)
            t.start()

    # [OK] 初始化数据库索引（优化查询性能）- 仅对 EXE 和 MINE 模式生效
    if _RUN_TYPE in [ 'MINE']:
        initialize_all_indexes()
    # initialize_all_indexes()

    # [NEW] 初始化数据库连接池
    print("=" * 60)
    print("[DB] 初始化数据库连接池...")
    try:
        # 为常用数据库预创建连接池
        get_db_pool(QUERY_DB_ADMIN, pool_size=5)
        get_db_pool(QUERY_DB_USER, pool_size=5)
        get_db_pool(DIALECTS_DB_ADMIN, pool_size=10)
        get_db_pool(DIALECTS_DB_USER, pool_size=10)
        get_db_pool(CHARACTERS_DB_PATH, pool_size=5)
        print("[OK] 数据库连接池初始化完成")
    except Exception as e:
        print(f" 连接池初始化失败: {str(e)}")
    print("=" * 60)

    # [新增] 启动时清理旧的临时文件（12小时前的）
    from app.tools.file_manager import file_manager
    print("=" * 60)
    print("[CLEANUP] 清理旧的临时文件（12小时前）...")
    try:
        deleted_count = file_manager.cleanup_old_files(max_age_hours=12)
        print(f"[OK] 已清理 {deleted_count} 个过期任务目录")
    except Exception as e:
        print(f" 清理临时文件失败: {str(e)}")
    print("=" * 60)

    # [新增] 预热方言数据缓存（避免第一个请求超时）
    from app.service.match_input_tip import _load_dialect_cache
    print("=" * 60)
    print(" 预热方言数据缓存...")
    try:
        # 预加载管理员和用户数据库的缓存
        _load_dialect_cache(QUERY_DB_ADMIN, filter_valid_abbrs_only=True)
        _load_dialect_cache(QUERY_DB_USER, filter_valid_abbrs_only=True)
        _load_dialect_cache(QUERY_DB_ADMIN, filter_valid_abbrs_only=False)
        _load_dialect_cache(QUERY_DB_USER, filter_valid_abbrs_only=False)
        print("[OK] 方言数据缓存预热完成（4个缓存已加载）")
    except Exception as e:
        print(f" 缓存预热失败: {str(e)}")
    print("=" * 60)

    # [已注释] 执行日志数据迁移（从 txt 到 logs.db）
    # print("=" * 60)1
    # print("[TASK] 检查日志数据迁移...")
    # run_migration(force=False)  # 只迁移一次，不强制重复
    # print("=" * 60)

    # 获取数据库连接，并启动日志线程
    # [FIX] 只在非 gunicorn 环境下启动后台线程
    # 在 gunicorn 环境下，后台线程由主进程启动（见 gunicorn_config.py）
    db = next(get_db())

    # 检测是否在 gunicorn worker 进程中
    is_gunicorn_worker = os.environ.get('SERVER_SOFTWARE', '').startswith('gunicorn')

    if not is_gunicorn_worker:
        # 非 gunicorn 环境（如 uvicorn 直接运行），启动后台线程
        print(" [单进程模式] 启动后台线程...")
        start_api_logger_workers(db)
        # [NEW] 启动用户活动更新后台线程
        start_user_activity_writer()

        # [OK] 启动定时任务调度器（只在单进程模式下启动）
        start_scheduler()

        # [新增] 启动定期批量清理任务（每小时检查一次，清理3小时前的文件）
        cleanup_thread = threading.Thread(target=_periodic_cleanup, daemon=True)
        cleanup_thread.start()
        print("[TASK] 已启动定期清理线程（每小时执行，清理3小时前文件）")
    else:
        # gunicorn 环境，跳过（由主进程启动）
        print("[SKIP]  [Worker进程] 跳过后台线程启动（已由主进程启动）")

    try:
        yield  # 应用运行中
    finally:
        # [FIX] 只在非 gunicorn worker 环境下停止后台线程
        # 在 gunicorn 环境下，后台线程由主进程管理，worker 重启不应停止它们
        if not is_gunicorn_worker:
            # 停止日志写入线程
            stop_api_logger_workers()

            # [NEW] 停止用户活动更新线程
            stop_user_activity_writer()

            # [OK] 停止定时任务调度器
            stop_scheduler()

            print("[STOP] [单进程模式] 后台线程已停止")
        else:
            print("[SKIP]  [Worker进程] 跳过后台线程停止（由主进程管理）")

        print("[STOP] App shutting down...")
        await close_redis()  # [OK] 關閉 Redis 連接

        # [NEW] 关闭所有数据库连接池
        print("[DB] 关闭数据库连接池...")
        close_all_pools()
        print("[OK] 数据库连接池已关闭")


def _periodic_cleanup():
    """定期批量清理旧文件（每小时执行一次，清理3小时前的文件）"""
    from app.tools.file_manager import file_manager
    while True:
        time.sleep(3600)  # 每小时执行一次
        try:
            deleted_count = file_manager.cleanup_old_files(max_age_hours=3)
            if deleted_count > 0:
                now = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{now}] [CLEANUP] 定期清理：已删除 {deleted_count} 个过期任务目录（超过3小时）")
        except Exception as e:
            print(f"[CLEANUP] 定期清理失败: {str(e)}")


if _RUN_TYPE in ['EXE', 'MINE']:
    app = FastAPI(lifespan=lifespan)
else:
    app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)

# 允許跨域
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

#  自动 gzip 压缩（基于 Accept-Encoding 请求头）
# minimum_size=1024 表示只压缩大于 1KB 的响应
app.add_middleware(GZipMiddleware, minimum_size=1024)

# API 日志记录中间件（在 TrafficLoggingMiddleware 之前）
app.add_middleware(ApiLoggingMiddleware)

# api統計
app.add_middleware(TrafficLoggingMiddleware)

if _RUN_TYPE == 'EXE':
    # === 活動請求統計中介層 ===
    @app.middleware("http")
    async def pause_print_while_request(request: Request, call_next):
        global active_requests
        with print_lock:
            active_requests += 1
        try:
            response = await call_next(request)
            return response
        finally:
            with print_lock:
                active_requests -= 1

# === 掛載子路由與靜態資源 ===
setup_routes(app)

app.mount("", StaticFiles(directory=os.path.abspath("app/statics"), html=True), name="static")

# app.mount("/css", StaticFiles(directory=get_resource_path("app/statics/css")), name="css")
# app.mount("/js", StaticFiles(directory=get_resource_path("app/statics/js")), name="js")
# app.mount("/app/service", StaticFiles(directory=get_resource_path("app/service")), name="make")
# app.mount("/data", StaticFiles(directory=get_resource_path("data")), name="data")
if _RUN_TYPE == 'EXE':
    app.mount("/data", StaticFiles(directory=ensure_user_data()), name="data")
