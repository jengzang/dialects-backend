"""
Gunicorn config.

Master process:
- start/stop scheduler once
- start/stop logging worker threads (shared across all workers via multiprocessing.Queue)

Worker process:
- cleanup DB pools on worker exit
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def on_starting(server):
    """
    在 Gunicorn 主进程启动时执行（只执行一次）
    在这里启动后台线程，所有 worker 进程将通过 multiprocessing.Queue 共享这些队列
    """
    from app.logging.tasks.scheduler import start_scheduler
    from app.logging.middleware.traffic_logging import start_api_logger_workers
    from app.auth.service import start_user_activity_writer

    print("=" * 60)
    print("[Gunicorn Master] starting background workers...")
    print("=" * 60)

    # 启动日志后台线程（在主进程中，使用 multiprocessing.Queue 与 worker 通信）
    start_api_logger_workers()

    # 启动用户活动更新后台线程
    start_user_activity_writer()

    # 启动定时任务调度器
    start_scheduler()

    print("=" * 60)
    print("[Gunicorn Master] background workers started")
    print("  - 6 logging threads (using multiprocessing.Queue)")
    print("  - 1 user activity thread")
    print("  - 1 scheduler")
    print("=" * 60)


def post_worker_init(worker):
    """Worker 初始化时执行（不再启动日志线程）"""
    print(f"[Worker {worker.pid}] initialized")


def worker_exit(server, worker):
    """Worker 退出时清理资源"""
    print(f"[Worker {worker.pid}] exiting, cleaning up resources...")

    try:
        from app.sql.db_pool import close_all_pools
        close_all_pools()
    except Exception as e:
        print(f"[Worker {worker.pid}] close_all_pools failed: {e}")


def on_exit(server):
    """
    在 Gunicorn 主进程退出时执行
    停止所有后台线程
    """
    from app.logging.tasks.scheduler import stop_scheduler
    from app.logging.middleware.traffic_logging import stop_api_logger_workers
    from app.auth.service import stop_user_activity_writer

    print("=" * 60)
    print("[Gunicorn Master] stopping background workers...")
    print("=" * 60)

    try:
        stop_api_logger_workers()
    except Exception as e:
        print(f"[Gunicorn Master] stop_api_logger_workers failed: {e}")

    try:
        stop_user_activity_writer()
    except Exception as e:
        print(f"[Gunicorn Master] stop_user_activity_writer failed: {e}")

    try:
        stop_scheduler()
    except Exception as e:
        print(f"[Gunicorn Master] stop_scheduler failed: {e}")

    print("=" * 60)
    print("[Gunicorn Master] background workers stopped")
    print("=" * 60)


bind = "0.0.0.0:5000"
workers = 3
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 300
max_requests = 1000
max_requests_jitter = 50
graceful_timeout = 60
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
