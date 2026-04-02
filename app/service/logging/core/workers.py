import threading

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
_start_lock = threading.Lock()


def start_api_logger_workers():
    """Start all background logging workers once."""
    global _workers_started
    with _start_lock:
        if _workers_started:
            return

        if ENABLE_API_KEYWORD_LOGGING:
            threading.Thread(target=keyword_log_writer, daemon=True).start()

        threading.Thread(target=diagnostic_event_writer, daemon=True).start()
        threading.Thread(target=statistics_writer, daemon=True).start()
        threading.Thread(target=html_visit_writer, daemon=True).start()
        threading.Thread(target=log_writer_thread, daemon=True).start()
        threading.Thread(target=summary_writer, daemon=True).start()
        threading.Thread(target=online_time_writer, daemon=True).start()

        _workers_started = True
        print("[OK] API logger workers started")


def stop_api_logger_workers():
    """Stop all background logging workers."""
    for q in (
        keyword_log_queue,
        diagnostic_queue,
        statistics_queue,
        html_visit_queue,
        log_queue,
        summary_queue,
        online_time_queue,
    ):
        try:
            q.put_nowait(None)
        except Exception:
            pass

    print("[OK] API logger workers stopped")
