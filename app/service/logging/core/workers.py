import logging
import threading
import time
from queue import Full

from app.service.logging.config import ENABLE_API_KEYWORD_LOGGING
from app.service.logging.core.queues import (
    diagnostic_queue,
    html_visit_queue,
    keyword_log_queue,
    log_queue,
    online_time_queue,
    statistics_queue,
    summary_queue,
)
from app.service.logging.stats.auth_usage_pipeline import log_writer_thread, summary_writer
from app.service.logging.stats.diagnostic_pipeline import diagnostic_event_writer
from app.service.logging.stats.html_visit_pipeline import html_visit_writer
from app.service.logging.stats.keyword_pipeline import keyword_log_writer
from app.service.logging.stats.online_time_pipeline import online_time_writer
from app.service.logging.stats.usage_pipeline import statistics_writer

_workers_started = False
_workers_stopping = False
_start_lock = threading.Lock()
_worker_threads = []
_stop_requested = set()
logger = logging.getLogger(__name__)


def start_api_logger_workers():
    """Start all background logging workers once."""
    global _workers_started
    with _start_lock:
        if _workers_stopping:
            raise RuntimeError("Logging shutdown is incomplete; finish stop_api_logger_workers() before restarting")
        if _workers_started:
            return

        targets = [
            (diagnostic_queue, diagnostic_event_writer),
            (statistics_queue, statistics_writer),
            (html_visit_queue, html_visit_writer),
            (log_queue, log_writer_thread),
            (summary_queue, summary_writer),
            (online_time_queue, online_time_writer),
        ]
        if ENABLE_API_KEYWORD_LOGGING:
            targets.insert(0, (keyword_log_queue, keyword_log_writer))
        for q, target in targets:
            thread = threading.Thread(target=target, name=target.__name__, daemon=True)
            thread.start()
            _worker_threads.append((q, thread))
        _workers_started = True
        print("[OK] API logger workers started")


def stop_api_logger_workers(timeout: float = 30.0) -> bool:
    """Drain active workers within one deadline; callers must stop producers first."""
    global _workers_started, _workers_stopping
    deadline = time.monotonic() + max(0.0, timeout)
    with _start_lock:
        _workers_stopping = True
        for q, thread in _worker_threads:
            if thread in _stop_requested:
                continue
            while thread.is_alive():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    q.put(None, timeout=min(0.1, remaining))
                except Full:
                    continue
                except Exception:
                    logger.exception("[AUTH_USAGE_SHUTDOWN] Failed to signal %s", thread.name)
                    break
                _stop_requested.add(thread)
                break
        for _, thread in _worker_threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        _worker_threads[:] = [(q, thread) for q, thread in _worker_threads if thread.is_alive()]
        _stop_requested.intersection_update(thread for _, thread in _worker_threads)
        _workers_started = bool(_worker_threads)
        if _workers_started:
            logger.error(
                "[AUTH_USAGE_SHUTDOWN] Deadline exceeded; workers still running: %s. Buffered events remain at risk",
                ", ".join(thread.name for _, thread in _worker_threads),
            )
            return False
        _workers_stopping = False
        print("[OK] API logger workers stopped after draining")
        return True
