"""
Gunicorn config.

Master process:
- start/stop scheduler once

Worker process:
- start/stop in-process queue writer threads
- cleanup DB pools on worker exit
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def on_starting(server):
    from app.logging.tasks.scheduler import start_scheduler

    print("=" * 60)
    print("[Gunicorn Master] starting scheduler...")
    print("=" * 60)
    start_scheduler()


def post_worker_init(worker):
    from app.logging.middleware.traffic_logging import start_api_logger_workers
    from app.auth.service import start_user_activity_writer

    print(f"[Worker {worker.pid}] starting writer workers...")
    start_api_logger_workers()
    start_user_activity_writer()


def worker_exit(server, worker):
    from app.logging.middleware.traffic_logging import stop_api_logger_workers
    from app.auth.service import stop_user_activity_writer

    print(f"[Worker {worker.pid}] stopping writer workers...")
    try:
        stop_api_logger_workers()
    except Exception as e:
        print(f"[Worker {worker.pid}] stop_api_logger_workers failed: {e}")

    try:
        stop_user_activity_writer()
    except Exception as e:
        print(f"[Worker {worker.pid}] stop_user_activity_writer failed: {e}")

    try:
        from app.sql.db_pool import close_all_pools
        close_all_pools()
    except Exception as e:
        print(f"[Worker {worker.pid}] close_all_pools failed: {e}")


def on_exit(server):
    from app.logging.tasks.scheduler import stop_scheduler

    print("=" * 60)
    print("[Gunicorn Master] stopping scheduler...")
    print("=" * 60)
    try:
        stop_scheduler()
    except Exception as e:
        print(f"[Gunicorn Master] stop_scheduler failed: {e}")


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
