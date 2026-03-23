# logs/scheduler.py
"""Scheduled maintenance and aggregation tasks for the logging system."""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import and_, text

from app.common.time_utils import now_shanghai, now_utc_naive, shanghai_to_utc_naive
from app.service.auth.database.connection import SessionLocal as AuthSessionLocal
from app.service.auth.database.models import ApiUsageLog
from app.service.auth.security.key_manager import cleanup_expired_keys
from app.service.auth.session.cleanup import (
    cleanup_excess_tokens_per_session,
    cleanup_expired_sessions,
    cleanup_revoked_tokens,
    cleanup_suspicious_sessions,
)
from app.service.logging.core.database import SessionLocal
from app.service.logging.core.models import ApiKeywordLog, ApiStatistics, ApiVisitLog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def cleanup_old_logs() -> None:
    """Delete old log data while keeping aggregate total rows."""
    logger.info("[DEL] Cleaning old log data...")
    db = SessionLocal()

    try:
        keyword_cutoff = now_utc_naive() - timedelta(days=365)
        local_bucket_cutoff = now_shanghai().replace(tzinfo=None) - timedelta(days=365)

        deleted_keywords = db.query(ApiKeywordLog).filter(
            ApiKeywordLog.timestamp < keyword_cutoff
        ).delete()

        deleted_visits = db.query(ApiVisitLog).filter(
            and_(
                ApiVisitLog.date.isnot(None),
                ApiVisitLog.date < local_bucket_cutoff,
            )
        ).delete()

        deleted_stats = db.query(ApiStatistics).filter(
            and_(
                ApiStatistics.stat_type == "keyword_daily",
                ApiStatistics.date < local_bucket_cutoff,
            )
        ).delete()

        db.commit()
        logger.info(
            "[OK] Cleanup finished: removed %s keyword logs, %s visit stats rows, %s daily keyword stats",
            deleted_keywords,
            deleted_visits,
            deleted_stats,
        )
    except Exception as exc:
        logger.error("[X] Failed to clean old logs: %s", exc)
        db.rollback()
    finally:
        db.close()


def cleanup_old_api_usage_logs() -> None:
    """Delete old API usage rows from auth.db."""
    logger.info("[DEL] Cleaning ApiUsageLog rows in auth.db...")
    db = AuthSessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        deleted_count = db.query(ApiUsageLog).filter(
            ApiUsageLog.called_at < cutoff_date
        ).delete()
        db.commit()
        logger.info("[OK] ApiUsageLog cleanup finished: removed %s rows", deleted_count)
    except Exception as exc:
        logger.error("[X] ApiUsageLog cleanup failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def aggregate_keyword_statistics() -> None:
    """Rebuild keyword total and keyword daily aggregates."""
    logger.info("[DB] Aggregating keyword statistics...")
    db = SessionLocal()

    try:
        db.query(ApiStatistics).filter(
            ApiStatistics.stat_type.in_(["keyword_total", "keyword_daily"])
        ).delete()

        db.execute(
            text(
                """
                INSERT INTO api_statistics (stat_type, date, category, item, count, updated_at)
                SELECT
                    'keyword_total' as stat_type,
                    NULL as date,
                    field as category,
                    value as item,
                    COUNT(*) as count,
                    datetime('now') as updated_at
                FROM api_keyword_log
                GROUP BY field, value
                """
            )
        )

        seven_days_ago = shanghai_to_utc_naive(now_shanghai() - timedelta(days=7))
        db.execute(
            text(
                """
                INSERT INTO api_statistics (stat_type, date, category, item, count, updated_at)
                SELECT
                    'keyword_daily' as stat_type,
                    DATE(datetime(timestamp, '+8 hours')) as date,
                    field as category,
                    value as item,
                    COUNT(*) as count,
                    datetime('now') as updated_at
                FROM api_keyword_log
                WHERE timestamp >= :cutoff_date
                GROUP BY DATE(datetime(timestamp, '+8 hours')), field, value
                """
            ),
            {"cutoff_date": seven_days_ago},
        )

        db.commit()

        from sqlalchemy import func

        keyword_total = db.query(func.count(ApiStatistics.id)).filter(
            ApiStatistics.stat_type == "keyword_total"
        ).scalar()
        keyword_daily = db.query(func.count(ApiStatistics.id)).filter(
            ApiStatistics.stat_type == "keyword_daily"
        ).scalar()

        logger.info(
            "[OK] Keyword aggregation finished: total=%s daily=%s",
            keyword_total,
            keyword_daily,
        )
    except Exception as exc:
        logger.error("[X] Keyword aggregation failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def start_scheduler() -> None:
    """Start background scheduled jobs."""
    scheduler.add_job(
        cleanup_old_logs,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="cleanup_old_logs",
        name="cleanup_old_logs",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_old_api_usage_logs,
        CronTrigger(hour=3, minute=30),
        id="cleanup_old_api_usage_logs",
        name="cleanup_old_api_usage_logs",
        replace_existing=True,
    )

    scheduler.add_job(
        aggregate_keyword_statistics,
        CronTrigger(minute=5),
        id="aggregate_keyword_stats",
        name="aggregate_keyword_stats",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_revoked_tokens,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="cleanup_revoked_tokens",
        name="cleanup_revoked_tokens",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_expired_sessions,
        CronTrigger(hour=2, minute=0),
        id="revoke_expired_sessions",
        name="revoke_expired_sessions",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_suspicious_sessions,
        CronTrigger(minute=15),
        id="check_suspicious_sessions",
        name="check_suspicious_sessions",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_excess_tokens_per_session,
        CronTrigger(hour=4, minute=0),
        id="cleanup_excess_tokens",
        name="cleanup_excess_tokens",
        replace_existing=True,
    )

    scheduler.add_job(
        cleanup_expired_keys,
        CronTrigger(hour=1, minute=0),
        id="cleanup_expired_keys",
        name="cleanup_expired_keys",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("[OK] Scheduler started")
    logger.info("   - cleanup_old_logs: Sun 03:00")
    logger.info("   - cleanup_old_api_usage_logs: daily 03:30")
    logger.info("   - aggregate_keyword_stats: hourly minute 05")
    logger.info("   - cleanup_revoked_tokens: Sun 03:00")
    logger.info("   - revoke_expired_sessions: daily 02:00")
    logger.info("   - check_suspicious_sessions: hourly minute 15")
    logger.info("   - cleanup_excess_tokens: daily 04:00")
    logger.info("   - cleanup_expired_keys: daily 01:00")


def stop_scheduler() -> None:
    """Stop background scheduled jobs."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[OK] Scheduler stopped")


def run_task_now(task_name: str) -> None:
    """Run a maintenance task immediately."""
    if task_name == "cleanup":
        cleanup_old_logs()
    elif task_name == "aggregate":
        aggregate_keyword_statistics()
    else:
        raise ValueError(f"Unknown task name: {task_name}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        run_task_now(sys.argv[1])
    else:
        print("Usage:")
        print("  python -m app.logging.scheduler cleanup")
        print("  python -m app.logging.scheduler aggregate")
