"""
Praat service cleanup scheduler (memory version - no database).

Automatically cleans up old uploads and tasks from memory and disk.
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
import shutil

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.praat.memory_store import task_store, upload_store
from app.praat.config import (
    CLEANUP_ENABLED,
    TASK_RETENTION_SECONDS,
    UPLOAD_RETENTION_SECONDS,
    CLEANUP_SCHEDULE_MINUTES,
    STORAGE_BASE_DIR
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create scheduler
scheduler = BackgroundScheduler()

# Storage base directory
STORAGE_BASE = STORAGE_BASE_DIR


def cleanup_memory_and_files():
    """
    Clean up old tasks and uploads from memory and disk.

    Deletion policy:
    - Tasks older than TASK_RETENTION_SECONDS
    - Uploads older than UPLOAD_RETENTION_SECONDS
    - Associated files on disk
    """
    logger.info("[PRAAT CLEANUP] Starting cleanup...")

    try:
        # Cleanup tasks
        deleted_tasks = task_store.cleanup_old_tasks(TASK_RETENTION_SECONDS)
        logger.info(f"[PRAAT CLEANUP] Deleted {deleted_tasks} old tasks from memory")

        # Cleanup uploads and files
        deleted_uploads = 0
        freed_bytes = 0

        # Get all uploads before cleanup
        all_uploads = []
        for upload_id in list(upload_store._uploads.keys()):
            upload = upload_store.get_upload(upload_id)
            if upload:
                all_uploads.append(upload)

        # Check each upload
        cutoff_time = datetime.utcnow() - timedelta(seconds=UPLOAD_RETENTION_SECONDS)

        for upload in all_uploads:
            created = datetime.fromisoformat(upload["created_at"])
            age = (datetime.utcnow() - created).total_seconds()

            if age > UPLOAD_RETENTION_SECONDS:
                # Delete files
                upload_dir = STORAGE_BASE / upload["id"]
                if upload_dir.exists():
                    try:
                        # Calculate size before deletion
                        size = sum(f.stat().st_size for f in upload_dir.rglob('*') if f.is_file())
                        freed_bytes += size

                        shutil.rmtree(upload_dir, ignore_errors=True)
                        logger.info(f"[PRAAT CLEANUP] Deleted files for upload {upload['id']} ({size / 1024 / 1024:.2f} MB)")
                    except Exception as e:
                        logger.error(f"[PRAAT CLEANUP] Failed to delete files for upload {upload['id']}: {e}")

                # Delete from memory
                upload_store.delete_upload(upload["id"])
                deleted_uploads += 1

        logger.info(
            f"[PRAAT CLEANUP] Cleanup complete: "
            f"deleted {deleted_uploads} uploads, "
            f"freed {freed_bytes / 1024 / 1024:.2f} MB"
        )

    except Exception as e:
        logger.error(f"[PRAAT CLEANUP] Cleanup failed: {e}")


def cleanup_orphaned_files():
    """
    Clean up orphaned files (files without memory records).

    This handles cases where memory records were lost but files remain.
    """
    logger.info("[PRAAT CLEANUP] Starting cleanup of orphaned files...")

    if not STORAGE_BASE.exists():
        logger.info("[PRAAT CLEANUP] Storage directory does not exist, skipping")
        return

    try:
        # Get all upload IDs from memory
        valid_upload_ids = set(upload_store._uploads.keys())

        # Check all directories in storage
        orphaned_count = 0
        freed_bytes = 0

        for upload_dir in STORAGE_BASE.iterdir():
            if not upload_dir.is_dir():
                continue

            upload_id = upload_dir.name

            # If directory doesn't have a corresponding memory record
            if upload_id not in valid_upload_ids:
                try:
                    # Calculate size
                    size = sum(f.stat().st_size for f in upload_dir.rglob('*') if f.is_file())
                    freed_bytes += size

                    shutil.rmtree(upload_dir, ignore_errors=True)
                    logger.info(f"[PRAAT CLEANUP] Deleted orphaned directory {upload_id} ({size / 1024 / 1024:.2f} MB)")
                    orphaned_count += 1
                except Exception as e:
                    logger.error(f"[PRAAT CLEANUP] Failed to delete orphaned directory {upload_id}: {e}")

        logger.info(
            f"[PRAAT CLEANUP] Orphaned cleanup complete: "
            f"deleted {orphaned_count} directories, "
            f"freed {freed_bytes / 1024 / 1024:.2f} MB"
        )

    except Exception as e:
        logger.error(f"[PRAAT CLEANUP] Orphaned cleanup failed: {e}")


def start_scheduler():
    """Start the cleanup scheduler."""
    if not CLEANUP_ENABLED:
        logger.info("[PRAAT CLEANUP] Cleanup is disabled in config")
        return

    # Run cleanup every N minutes
    scheduler.add_job(
        cleanup_memory_and_files,
        IntervalTrigger(minutes=CLEANUP_SCHEDULE_MINUTES),
        id="praat_cleanup_memory",
        name="Clean up old Praat tasks and uploads",
        replace_existing=True
    )
    logger.info(
        f"[PRAAT CLEANUP] Scheduled cleanup every {CLEANUP_SCHEDULE_MINUTES} minutes "
        f"(deletes data older than {TASK_RETENTION_SECONDS}s)"
    )

    # Run orphaned file cleanup every 2 hours
    scheduler.add_job(
        cleanup_orphaned_files,
        IntervalTrigger(hours=2),
        id="praat_cleanup_orphaned_files",
        name="Clean up orphaned Praat files",
        replace_existing=True
    )
    logger.info("[PRAAT CLEANUP] Scheduled orphaned cleanup every 2 hours")

    scheduler.start()
    logger.info("[PRAAT CLEANUP] Scheduler started (memory mode)")


def stop_scheduler():
    """Stop the cleanup scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[PRAAT CLEANUP] Scheduler stopped")
