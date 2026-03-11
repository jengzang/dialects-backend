# logs/scheduler.py
"""
日志系统定时任务

功能：
1. 每周清理 30 天前的旧日志
2. 每小时聚合关键词统计
3. Session和Token自动清理
4. SECRET_KEY自动清理
"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import and_, text

from app.service.logging.core.database import SessionLocal
from app.service.logging.core.models import ApiKeywordLog, ApiStatistics, ApiVisitLog
from app.service.auth.database import SessionLocal as AuthSessionLocal
from app.service.auth.models import ApiUsageLog
from app.service.auth.session_cleanup import (  # ✅ 导入session清理函数
    cleanup_revoked_tokens,
    cleanup_expired_sessions,
    cleanup_suspicious_sessions,
    cleanup_excess_tokens_per_session
)
from app.service.auth.key_manager import cleanup_expired_keys  # ✅ 导入key清理函数

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建调度器
scheduler = BackgroundScheduler()


def cleanup_old_logs():
    """
    清理旧日志任务

    删除 30 天前的：
    - api_keyword_log 记录
    - api_visit_log 每日统计（保留总计，date=NULL）
    - api_statistics 每日统计（保留总计）
    """
    logger.info("[DEL] 开始清理旧日志...")
    db = SessionLocal()

    try:
        cutoff_date = datetime.now() - timedelta(days=365)

        # 删除关键词日志
        deleted_keywords = db.query(ApiKeywordLog).filter(
            ApiKeywordLog.timestamp < cutoff_date
        ).delete()

        # 删除 HTML 访问每日统计（保留总计）
        deleted_visits = db.query(ApiVisitLog).filter(
            and_(
                ApiVisitLog.date.isnot(None),  # 只删除每日统计
                ApiVisitLog.date < cutoff_date
            )
        ).delete()

        # 删除每日统计（保留总计）
        deleted_stats = db.query(ApiStatistics).filter(
            and_(
                ApiStatistics.stat_type.in_(["keyword_daily", "usage_daily"]),
                ApiStatistics.date < cutoff_date
            )
        ).delete()

        db.commit()

        logger.info(f"[OK] 清理完成: 删除了 {deleted_keywords} 条关键词日志, {deleted_visits} 条访问统计, {deleted_stats} 条每日统计")

    except Exception as e:
        logger.error(f"[X] 清理旧日志失败: {e}")
        db.rollback()
    finally:
        db.close()


def cleanup_old_api_usage_logs():
    """
    清理 auth.db 中的 API 使用日志（ApiUsageLog）
    保留最近 7 天，避免日志表持续膨胀。
    """
    logger.info("[DEL] 开始清理 auth.db 的 ApiUsageLog...")
    db = AuthSessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        deleted_count = db.query(ApiUsageLog).filter(
            ApiUsageLog.called_at < cutoff_date
        ).delete()
        db.commit()
        logger.info(f"[OK] ApiUsageLog 清理完成: 删除 {deleted_count} 条")
    except Exception as e:
        logger.error(f"[X] ApiUsageLog 清理失败: {e}")
        db.rollback()
    finally:
        db.close()


def aggregate_keyword_statistics():
    """
    聚合关键词统计任务

    重新聚合：
    - keyword_total: 总计统计
    - keyword_daily: 最近 7 天的每日统计
    """
    logger.info("[DB] 开始聚合关键词统计...")
    db = SessionLocal()

    try:
        # 清空现有关键词统计
        db.query(ApiStatistics).filter(
            ApiStatistics.stat_type.in_(["keyword_total", "keyword_daily"])
        ).delete()

        # 聚合总计
        db.execute(text("""
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
        """))

        # 聚合最近 7 天的每日统计
        seven_days_ago = datetime.now() - timedelta(days=7)
        db.execute(text("""
            INSERT INTO api_statistics (stat_type, date, category, item, count, updated_at)
            SELECT
                'keyword_daily' as stat_type,
                DATE(timestamp) as date,
                field as category,
                value as item,
                COUNT(*) as count,
                datetime('now') as updated_at
            FROM api_keyword_log
            WHERE timestamp >= :cutoff_date
            GROUP BY DATE(timestamp), field, value
        """), {"cutoff_date": seven_days_ago})

        db.commit()

        # 统计结果
        from sqlalchemy import func
        keyword_total = db.query(func.count(ApiStatistics.id)).filter(
            ApiStatistics.stat_type == "keyword_total"
        ).scalar()

        keyword_daily = db.query(func.count(ApiStatistics.id)).filter(
            ApiStatistics.stat_type == "keyword_daily"
        ).scalar()

        logger.info(f"[OK] 聚合完成: 总计 {keyword_total} 条, 每日 {keyword_daily} 条")

    except Exception as e:
        logger.error(f"[X] 聚合统计失败: {e}")
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    """启动定时任务调度器"""
    # ========== 日志清理任务 ==========
    # 每周日凌晨 3 点清理旧日志
    scheduler.add_job(
        cleanup_old_logs,
        CronTrigger(day_of_week='sun', hour=3, minute=0),
        id='cleanup_old_logs',
        name='清理365天前的旧日志',
        replace_existing=True
    )

    # 每天凌晨 3:30 清理 auth.db 的 ApiUsageLog（保留7天）
    scheduler.add_job(
        cleanup_old_api_usage_logs,
        CronTrigger(hour=3, minute=30),
        id='cleanup_old_api_usage_logs',
        name='清理7天前的 ApiUsageLog',
        replace_existing=True
    )

    # 每小时的第 5 分钟聚合关键词统计
    scheduler.add_job(
        aggregate_keyword_statistics,
        CronTrigger(minute=5),
        id='aggregate_keyword_stats',
        name='聚合关键词统计',
        replace_existing=True
    )

    # ========== Session和Token清理任务 ==========
    # ✅ 每周日凌晨3点清理已撤销的token（保留7天历史）
    scheduler.add_job(
        cleanup_revoked_tokens,
        CronTrigger(day_of_week='sun', hour=3, minute=0),
        id='cleanup_revoked_tokens',
        name='清理已撤销的Token（每周）',
        replace_existing=True
    )

    # ✅ 每天凌晨2点标记过期session（不删除，只revoke）
    scheduler.add_job(
        cleanup_expired_sessions,
        CronTrigger(hour=2, minute=0),
        id='revoke_expired_sessions',
        name='撤销过期Session（每天）',
        replace_existing=True
    )

    # ✅ 每小时检测可疑会话
    scheduler.add_job(
        cleanup_suspicious_sessions,
        CronTrigger(minute=15),
        id='check_suspicious_sessions',
        name='检测可疑会话（每小时）',
        replace_existing=True
    )

    # ✅ 每天凌晨4点清理超量token
    scheduler.add_job(
        cleanup_excess_tokens_per_session,
        CronTrigger(hour=4, minute=0),
        id='cleanup_excess_tokens',
        name='清理超量Token（每天）',
        replace_existing=True
    )

    # ========== SECRET_KEY清理任务 ==========
    # ✅ 每天凌晨1点清理过期密钥
    scheduler.add_job(
        cleanup_expired_keys,
        CronTrigger(hour=1, minute=0),
        id='cleanup_expired_keys',
        name='清理过期SECRET_KEY',
        replace_existing=True
    )

    scheduler.start()
    logger.info("[OK] 定时任务调度器已启动")
    logger.info("   - 清理旧日志: 每周日 03:00")
    logger.info("   - 清理 ApiUsageLog: 每天 03:30（保留7天）")
    logger.info("   - 聚合统计: 每小时第 5 分钟")
    logger.info("   - 清理已撤销Token: 每周日 03:00")
    logger.info("   - 撤销过期Session: 每天 02:00")
    logger.info("   - 检测可疑会话: 每小时第 15 分钟")
    logger.info("   - 清理超量Token: 每天 04:00")
    logger.info("   - 清理过期密钥: 每天 01:00")


def stop_scheduler():
    """停止定时任务调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 定时任务调度器已停止")


def run_task_now(task_name: str):
    """
    立即执行指定任务（用于测试或手动触发）

    Args:
        task_name: 'cleanup' 或 'aggregate'
    """
    if task_name == 'cleanup':
        cleanup_old_logs()
    elif task_name == 'aggregate':
        aggregate_keyword_statistics()
    else:
        raise ValueError(f"未知的任务名: {task_name}")


# 可以直接运行此脚本来手动执行任务
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        task = sys.argv[1]
        run_task_now(task)
    else:
        print("用法:")
        print("  python -m app.logging.scheduler cleanup    # 清理旧日志")
        print("  python -m app.logging.scheduler aggregate  # 聚合统计")
