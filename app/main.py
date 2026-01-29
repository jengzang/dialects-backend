# app/main.py
import os
import threading
import time
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from app.auth.database import get_db
from app.redis_client import close_redis
from app.routes import setup_routes
from app.logs.api_logger import start_api_logger_workers, stop_api_logger_workers, TrafficLoggingMiddleware
from app.statics.static_utils import ensure_user_data  # 如果你要用它挂载静态资源
from common.config import _RUN_TYPE
from starlette.staticfiles import StaticFiles

# [OK] 导入日志迁移模块
# from app.logs.migrate_from_txt import run_migration
# [OK] 导入定时任务模块
from app.logs.scheduler import start_scheduler, stop_scheduler
# [OK] 导入数据库索引管理模块
from app.sql.index_manager import initialize_all_indexes

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
                    print(f"[{now}] Backend alive [OK] — 開發者: 不羈")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _RUN_TYPE == 'EXE':
        global _printer_started
        if not _printer_started:
            _printer_started = True
            t = threading.Thread(target=_periodic_printer, daemon=True)
            t.start()

    # [OK] 初始化数据库索引（优化查询性能）- 仅对 EXE 和 MINE 模式生效
    if _RUN_TYPE in ['EXE', 'MINE']:
        initialize_all_indexes()

    # [新增] 启动时清理旧的临时文件（12小时前的）
    from app.tools.file_manager import file_manager
    print("=" * 60)
    print("🧹 清理旧的临时文件（12小时前）...")
    try:
        deleted_count = file_manager.cleanup_old_files(max_age_hours=12)
        print(f"✅ 已清理 {deleted_count} 个过期任务目录")
    except Exception as e:
        print(f"⚠️ 清理临时文件失败: {str(e)}")
    print("=" * 60)

    # [已注释] 执行日志数据迁移（从 txt 到 logs.db）
    # print("=" * 60)
    # print("🔄 检查日志数据迁移...")
    # run_migration(force=False)  # 只迁移一次，不强制重复
    # print("=" * 60)

    # 获取数据库连接，并启动日志线程
    db = next(get_db())
    start_api_logger_workers(db)

    # [OK] 启动定时任务调度器
    start_scheduler()

    # [新增] 启动定期批量清理任务（每小时检查一次，清理12小时前的文件）
    cleanup_thread = threading.Thread(target=_periodic_cleanup, daemon=True)
    cleanup_thread.start()
    print("🔄 已启动定期清理线程（每小时执行，清理12小时前文件）")

    try:
        yield  # 应用运行中
    finally:
        # 停止日志写入线程
        stop_api_logger_workers()

        # [OK] 停止定时任务调度器
        stop_scheduler()

        print("🛑 App shutting down...")
        await close_redis()  # [OK] 關閉 Redis 連接


def _periodic_cleanup():
    """定期批量清理旧文件（每小时执行一次，清理12小时前的文件）"""
    from app.tools.file_manager import file_manager
    while True:
        time.sleep(3600)  # 每小时执行一次
        try:
            deleted_count = file_manager.cleanup_old_files(max_age_hours=12)
            if deleted_count > 0:
                now = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{now}] [CLEANUP] 定期清理：已删除 {deleted_count} 个过期任务目录（超过12小时）")
        except Exception as e:
            print(f"[CLEANUP] 定期清理失败: {str(e)}")


if _RUN_TYPE in ['EXE', 'MINE']:
    app = FastAPI(lifespan=lifespan)
else:
    app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)
# 允許跨域
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# api統計、json壓縮
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
