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

from app.common.numba_bootstrap import bootstrap_numba_threading_environment

# 让 gunicorn master 在加载配置阶段就准备好 numba 线程层环境，
# 这样后续 fork 出来的 worker 会继承同一套默认设置。
bootstrap_numba_threading_environment()

from app.lifecycle import (
    cleanup_worker_process,
    start_background_services,
    stop_background_services,
)


def on_starting(server):
    """
    Run once in the Gunicorn master process.
    """
    print("=" * 60)
    print("[Gunicorn Master] starting background workers...")
    print("=" * 60)

    start_background_services()

    print("=" * 60)
    print("[Gunicorn Master] background workers started")
    print("  - logging workers")
    print("  - scheduler")
    print("=" * 60)


def post_worker_init(worker):
    """Worker initialization hook."""
    print(f"[Worker {worker.pid}] initialized")


def worker_exit(server, worker):
    """Clean up per-worker resources."""
    print(f"[Worker {worker.pid}] exiting, cleaning up resources...")

    try:
        cleanup_worker_process()
    except Exception as e:
        print(f"[Worker {worker.pid}] close_all_pools failed: {e}")


def on_exit(server):
    """
    Stop background services in the Gunicorn master process.
    """
    print("=" * 60)
    print("[Gunicorn Master] stopping background workers...")
    print("=" * 60)

    try:
        stop_background_services()
    except Exception as e:
        print(f"[Gunicorn Master] stop_background_services failed: {e}")

    print("=" * 60)
    print("[Gunicorn Master] background workers stopped")
    print("=" * 60)


bind = "0.0.0.0:5000"
workers = 3
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 300
max_requests = 5000
max_requests_jitter = 100
graceful_timeout = 60
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
