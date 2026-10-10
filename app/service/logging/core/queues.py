import multiprocessing
import logging
from queue import Full

from app.service.logging.config.diagnostics import DIAGNOSTIC_QUEUE_MAXSIZE
from app.service.logging.core.auth_usage_recovery import AUTH_USAGE_QUEUE_NAMES, preserve_auth_usage


logger = logging.getLogger(__name__)


log_queue = multiprocessing.Queue(maxsize=2000)  # ApiUsageLog -> auth.db
keyword_log_queue = multiprocessing.Queue(maxsize=5000)  # ApiKeywordLog -> logs.db
statistics_queue = multiprocessing.Queue(maxsize=3000)  # API statistics -> logs.db
html_visit_queue = multiprocessing.Queue(maxsize=1000)  # HTML visit stats -> logs.db
summary_queue = multiprocessing.Queue(maxsize=1000)  # ApiUsageSummary -> auth.db
online_time_queue = multiprocessing.Queue(maxsize=1000)  # Online time reports -> auth.db
diagnostic_queue = multiprocessing.Queue(maxsize=DIAGNOSTIC_QUEUE_MAXSIZE)  # ApiDiagnosticEvent -> logs.db

QUEUE_PUT_TIMEOUT_SECONDS = 0.05


def enqueue_with_backpressure(q, item, queue_name: str) -> bool:
    """Return True only when queued; preserve overflowing auth events on disk."""
    try:
        q.put(item, timeout=QUEUE_PUT_TIMEOUT_SECONDS)
        return True
    except Exception as error:
        if queue_name in AUTH_USAGE_QUEUE_NAMES:
            try:
                preserve_auth_usage(
                    queue_name, [item],
                    reason="queue_full" if isinstance(error, Full) else "enqueue_failed",
                    error=error,
                )
            except Exception:
                logger.critical(
                    "[AUTH_USAGE_LOST] %s admission and recovery storage failed; event could not be saved",
                    queue_name, exc_info=True,
                )
            return False
        if not isinstance(error, Full):
            raise
        print(
            f"[WARN] {queue_name} is full after {int(QUEUE_PUT_TIMEOUT_SECONDS * 1000)}ms, dropping entry"
        )
        return False
