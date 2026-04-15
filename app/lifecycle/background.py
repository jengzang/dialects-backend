import threading

_cleanup_lock = threading.Lock()
_cleanup_thread = None
_cleanup_stop_event = None


def _periodic_cleanup(stop_event: threading.Event) -> None:
    from app.tools.file_manager import file_manager
    from app.tools.config import CLEANUP_SCAN_INTERVAL_SECONDS

    while not stop_event.wait(CLEANUP_SCAN_INTERVAL_SECONDS):
        try:
            summary = file_manager.cleanup_once()
            if summary["total_deleted"] > 0:
                print(
                    "[CLEANUP] Periodic cleanup removed "
                    f"{summary['total_deleted']} objects "
                    f"(tasks={summary['tasks_deleted']}, "
                    f"artifacts={summary['artifacts_deleted']}, "
                    f"capacity={summary['capacity_deleted']}, "
                    f"fallback={summary['fallback_deleted']})"
                )
        except Exception as exc:
            print(f"[CLEANUP] Periodic cleanup failed: {exc}")


def start_background_services() -> None:
    from app.service.logging.core.workers import start_api_logger_workers
    from app.service.logging.tasks import start_scheduler

    global _cleanup_thread, _cleanup_stop_event

    start_api_logger_workers()
    start_scheduler()

    with _cleanup_lock:
        if _cleanup_thread and _cleanup_thread.is_alive():
            return

        _cleanup_stop_event = threading.Event()
        _cleanup_thread = threading.Thread(
            target=_periodic_cleanup,
            args=(_cleanup_stop_event,),
            daemon=True,
            name="periodic_cleanup",
        )
        _cleanup_thread.start()

    print("[TASK] Started periodic cleanup thread")


def stop_background_services() -> None:
    from app.service.logging.core.workers import stop_api_logger_workers
    from app.service.logging.tasks import stop_scheduler

    global _cleanup_thread, _cleanup_stop_event

    with _cleanup_lock:
        stop_event = _cleanup_stop_event
        cleanup_thread = _cleanup_thread
        _cleanup_stop_event = None
        _cleanup_thread = None

    if stop_event is not None:
        stop_event.set()

    if cleanup_thread is not None and cleanup_thread.is_alive():
        cleanup_thread.join(timeout=1.0)

    stop_api_logger_workers()
    stop_scheduler()


def cleanup_worker_process() -> None:
    from app.sql.db_pool import close_all_pools

    close_all_pools()
