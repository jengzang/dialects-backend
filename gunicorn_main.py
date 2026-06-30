"""
Gunicorn config for main app.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.common.numba_bootstrap import bootstrap_numba_threading_environment

bootstrap_numba_threading_environment()

from app.lifecycle import (
    cleanup_worker_process,
    start_background_services,
    stop_background_services,
)


def on_starting(server):
    print("=" * 60)
    print("[Gunicorn Master: main] starting background workers...")
    print("=" * 60)
    start_background_services()
    print("=" * 60)
    print("[Gunicorn Master: main] background workers started")
    print("  - logging workers")
    print("  - scheduler")
    print("=" * 60)


def post_worker_init(worker):
    print(f"[Main Worker {worker.pid}] initialized")


def worker_exit(server, worker):
    print(f"[Main Worker {worker.pid}] exiting, cleaning up resources...")
    try:
        cleanup_worker_process()
    except Exception as e:
        print(f"[Main Worker {worker.pid}] close_all_pools failed: {e}")


def on_exit(server):
    print("=" * 60)
    print("[Gunicorn Master: main] stopping background workers...")
    print("=" * 60)
    try:
        stop_background_services()
    except Exception as e:
        print(f"[Gunicorn Master: main] stop_background_services failed: {e}")
    print("=" * 60)
    print("[Gunicorn Master: main] background workers stopped")
    print("=" * 60)


bind = "0.0.0.0:5000"
workers = 3
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 300
max_requests = 5000
max_requests_jitter = 200
graceful_timeout = 60
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
