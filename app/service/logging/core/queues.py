import multiprocessing
from queue import Full

from app.service.logging.config.diagnostics import DIAGNOSTIC_QUEUE_MAXSIZE


log_queue = multiprocessing.Queue(maxsize=2000)  # ApiUsageLog -> auth.db
keyword_log_queue = multiprocessing.Queue(maxsize=5000)  # ApiKeywordLog -> logs.db
statistics_queue = multiprocessing.Queue(maxsize=3000)  # API statistics -> logs.db
html_visit_queue = multiprocessing.Queue(maxsize=1000)  # HTML visit stats -> logs.db
summary_queue = multiprocessing.Queue(maxsize=1000)  # ApiUsageSummary -> auth.db
online_time_queue = multiprocessing.Queue(maxsize=1000)  # Online time reports -> auth.db
diagnostic_queue = multiprocessing.Queue(maxsize=DIAGNOSTIC_QUEUE_MAXSIZE)  # ApiDiagnosticEvent -> logs.db

QUEUE_PUT_TIMEOUT_SECONDS = 0.05


def enqueue_with_backpressure(q, item, queue_name: str) -> bool:
    """Try enqueue with short backpressure instead of immediate drop."""
    try:
        q.put(item, timeout=QUEUE_PUT_TIMEOUT_SECONDS)
        return True
    except Full:
        print(
            f"[WARN] {queue_name} is full after {int(QUEUE_PUT_TIMEOUT_SECONDS * 1000)}ms, dropping entry"
        )
        return False
