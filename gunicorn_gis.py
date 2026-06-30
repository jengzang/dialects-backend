"""
Gunicorn config for gis app.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.common.numba_bootstrap import bootstrap_numba_threading_environment

bootstrap_numba_threading_environment()

from app.lifecycle import cleanup_worker_process


def post_worker_init(worker):
    print(f"[GIS Worker {worker.pid}] initialized")


def worker_exit(server, worker):
    print(f"[GIS Worker {worker.pid}] exiting, cleaning up resources...")
    try:
        cleanup_worker_process()
    except Exception as e:
        print(f"[GIS Worker {worker.pid}] close_all_pools failed: {e}")


bind = "0.0.0.0:5001"
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 300
max_requests = 2000
max_requests_jitter = 100
graceful_timeout = 60
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
