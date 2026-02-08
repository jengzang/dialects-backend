"""
Praat service cleanup scheduler.

Automatically cleans up old uploads and completed jobs to prevent disk space exhaustion.
Runs every 30 minutes and deletes uploads older than 1 hour.
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
import shutil

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_

from app.praat.database import SessionLocal
from app.praat.models import Upload, Job
from app.praat.config import (
    CLEANUP_ENABLED,
    CLEANUP_AGE_HOURS,
    CLEANUP_SCHEDULE_MINUTES,
    ORPHANED_CLEANUP_ENABLED,
    ORPHANED_CLEANUP_HOURS,
    STORAGE_BASE_DIR
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create scheduler
scheduler = BackgroundScheduler()

# Storage base directory
STORAGE_BASE = STORAGE_BASE_DIR


def cleanup_old_uploads():
    """
    Clean up old uploads and completed jobs.

    Deletion policy:
    - Uploads older than 1 hour (configurable)
    - Completed/error/canceled jobs older than 1 hour
    - Failed uploads (no associated jobs)
    """
    logger.info("[PRAAT CLEANUP] Starting cleanup of old uploads...")
    db = SessionLocal()

    try:
        # Cutoff time: configurable hours ago
        cutoff_time = datetime.utcnow() - timedelta(hours=CLEANUP_AGE_HOURS)

        # Find old uploads
        old_uploads = db.query(Upload).filter(
            Upload.created_at < cutoff_time
        ).all()

        deleted_count = 0
        freed_bytes = 0

        for upload in old_uploads:
            # Check if all associated jobs are in terminal state
            active_jobs = db.query(Job).filter(
                and_(
                    Job.upload_id == upload.id,
                    Job.status.in_(["queued", "running"])
                )
            ).count()

            if active_jobs > 0:
                logger.info(f"[PRAAT CLEANUP] Skipping upload {upload.id} (has active jobs)")
                continue

            # Delete files
            upload_dir = STORAGE_BASE / upload.id
            if upload_dir.exists():
                try:
                    # Calculate size before deletion
                    size = sum(f.stat().st_size for f in upload_dir.rglob('*') if f.is_file())
                    freed_bytes += size

                    shutil.rmtree(upload_dir, ignore_errors=True)
                    logger.info(f"[PRAAT CLEANUP] Deleted files for upload {upload.id} ({size / 1024 / 1024:.2f} MB)")
                except Exception as e:
                    logger.error(f"[PRAAT CLEANUP] Failed to delete files for upload {upload.id}: {e}")

            # Delete from database (cascade will delete jobs)
            db.delete(upload)
            deleted_count += 1

        db.commit()

        logger.info(
            f"[PRAAT CLEANUP] Cleanup complete: "
            f"deleted {deleted_count} uploads, "
            f"freed {freed_bytes / 1024 / 1024:.2f} MB"
        )

    except Exception as e:
        logger.error(f"[PRAAT CLEANUP] Cleanup failed: {e}")
        db.rollback()
    finally:
        db.close()


def cleanup_orphaned_files():
    """
    Clean up orphaned files (files without database records).

    This handles cases where database records were deleted but files remain.
    """
    logger.info("[PRAAT CLEANUP] Starting cleanup of orphaned files...")

    if not STORAGE_BASE.exists():
        logger.info("[PRAAT CLEANUP] Storage directory does not exist, skipping")
        return

    db = SessionLocal()
    try:
        # Get all upload IDs from database
        valid_upload_ids = {upload.id for upload in db.query(Upload.id).all()}

        # Check all directories in storage
        orphaned_count = 0
        freed_bytes = 0

        for upload_dir in STORAGE_BASE.iterdir():
            if not upload_dir.is_dir():
                continue

            upload_id = upload_dir.name

            # If directory doesn't have a corresponding database record
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
    finally:
        db.close()


def start_scheduler():
    """Start the cleanup scheduler."""
    if not CLEANUP_ENABLED:
        logger.info("[PRAAT CLEANUP] Cleanup is disabled in config")
        return

    # Run cleanup every N minutes (frequent cleanup for short retention)
    scheduler.add_job(
        cleanup_old_uploads,
        IntervalTrigger(minutes=CLEANUP_SCHEDULE_MINUTES),
        id="praat_cleanup_old_uploads",
        name="Clean up old Praat uploads",
        replace_existing=True
    )
    logger.info(
        f"[PRAAT CLEANUP] Scheduled cleanup every {CLEANUP_SCHEDULE_MINUTES} minutes "
        f"(deletes uploads older than {CLEANUP_AGE_HOURS} hour(s))"
    )

    # Run orphaned file cleanup every N hours
    if ORPHANED_CLEANUP_ENABLED:
        scheduler.add_job(
            cleanup_orphaned_files,
            IntervalTrigger(hours=ORPHANED_CLEANUP_HOURS),
            id="praat_cleanup_orphaned_files",
            name="Clean up orphaned Praat files",
            replace_existing=True
        )
        logger.info(
            f"[PRAAT CLEANUP] Scheduled orphaned cleanup every {ORPHANED_CLEANUP_HOURS} hour(s)"
        )

    scheduler.start()
    logger.info("[PRAAT CLEANUP] Scheduler started")


def stop_scheduler():
    """Stop the cleanup scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[PRAAT CLEANUP] Scheduler stopped")
