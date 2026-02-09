"""
Gunicorn 配置文件
用于在主进程中启动后台线程，避免多 worker 重复启动
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def on_starting(server):
    """
    在 Gunicorn 主进程启动时执行（只执行一次）
    在这里启动后台线程，所有 worker 进程将共享这些队列
    """
    print("=" * 60)
    print("🚀 [Gunicorn Master] 启动后台线程...")
    print("=" * 60)

    # 导入必要的模块
    from app.auth.database import get_db
    from app.logs.service.api_logger import start_api_logger_workers
    from app.auth.service import start_user_activity_writer
    from app.logs.scheduler import start_scheduler

    # 获取数据库连接
    db = next(get_db())

    # 启动日志后台线程（在主进程中）
    start_api_logger_workers(db)

    # 启动用户活动更新后台线程（在主进程中）
    start_user_activity_writer()

    # 启动定时任务调度器（在主进程中）
    start_scheduler()

    print("=" * 60)
    print("✅ [Gunicorn Master] 后台线程启动完成")
    print("   - 5个日志线程（logs.db + auth.db）")
    print("   - 1个用户活动线程（auth.db）")
    print("   - 1个定时任务调度器")
    print("   - 总计：6个后台线程 + 1个调度器在主进程中运行")
    print("=" * 60)


def on_exit(server):
    """
    在 Gunicorn 主进程退出时执行
    停止所有后台线程
    """
    print("=" * 60)
    print("🛑 [Gunicorn Master] 停止后台线程...")
    print("=" * 60)

    from app.logs.service.api_logger import stop_api_logger_workers
    from app.auth.service import stop_user_activity_writer
    from app.logs.scheduler import stop_scheduler

    stop_api_logger_workers()
    stop_user_activity_writer()
    stop_scheduler()

    print("✅ [Gunicorn Master] 后台线程已停止")
    print("=" * 60)


# Gunicorn 配置参数
bind = "0.0.0.0:5000"
workers = 3
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 180
max_requests = 1000
max_requests_jitter = 50

# 日志配置
accesslog = "-"  # 输出到 stdout
errorlog = "-"   # 输出到 stderr
loglevel = "info"
