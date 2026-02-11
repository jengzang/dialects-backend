"""
自动迁移管理器 - Docker 友好
支持启动时自动检测和迁移数据库结构
"""
import os
import time
import logging
from contextlib import contextmanager
from sqlalchemy import inspect, text
from app.auth.database import engine, SessionLocal

logger = logging.getLogger(__name__)

# 环境变量控制
AUTO_MIGRATE = os.getenv("AUTO_MIGRATE", "true").lower() == "true"
MIGRATION_TIMEOUT = int(os.getenv("MIGRATION_TIMEOUT", "300"))  # 5分钟


@contextmanager
def migration_lock(db, timeout=MIGRATION_TIMEOUT):
    """
    迁移锁（防止多容器同时迁移）
    使用数据库表级锁
    """
    lock_acquired = False
    start_time = time.time()

    try:
        # 尝试获取锁（创建临时锁表）
        while time.time() - start_time < timeout:
            try:
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS _migration_lock (
                        id INTEGER PRIMARY KEY,
                        locked_at TEXT,
                        locked_by TEXT
                    )
                """))
                db.execute(text("""
                    INSERT INTO _migration_lock (id, locked_at, locked_by)
                    VALUES (1, datetime('now'), :hostname)
                """), {"hostname": os.getenv("HOSTNAME", "unknown")})
                db.commit()
                lock_acquired = True
                logger.info("[MIGRATE-LOCK] 获取迁移锁成功")
                print("[MIGRATE-LOCK] 获取迁移锁成功")
                break
            except Exception:
                # 锁被占用，等待
                logger.info("[MIGRATE-LOCK] 等待迁移锁...")
                print("[MIGRATE-LOCK] 等待迁移锁...")
                time.sleep(1)

        if not lock_acquired:
            raise TimeoutError("无法获取迁移锁（超时5分钟）")

        yield

    finally:
        if lock_acquired:
            # 释放锁
            try:
                db.execute(text("DELETE FROM _migration_lock WHERE id = 1"))
                db.commit()
                logger.info("[MIGRATE-LOCK] 释放迁移锁")
                print("[MIGRATE-LOCK] 释放迁移锁")
            except Exception as e:
                logger.warning(f"[MIGRATE-LOCK] 释放锁失败: {e}")


def check_migration_needed():
    """检查是否需要迁移"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    issues = []

    # 检查 secret_keys 表
    if 'secret_keys' not in tables:
        issues.append(("table", "secret_keys"))

    # 检查 sessions 表
    if 'sessions' not in tables:
        issues.append(("table", "sessions"))

    # 检查 refresh_tokens.session_id 列
    if 'refresh_tokens' in tables:
        columns = [col['name'] for col in inspector.get_columns('refresh_tokens')]
        if 'session_id' not in columns:
            issues.append(("column", "refresh_tokens.session_id"))
        if 'ip_address' not in columns:
            issues.append(("column", "refresh_tokens.ip_address"))
        if 'device_info' not in columns:
            issues.append(("column", "refresh_tokens.device_info"))

    return issues


def run_auto_migrate():
    """
    自动运行迁移（启动时调用）

    Returns:
        bool: 迁移是否成功
    """
    if not AUTO_MIGRATE:
        logger.info("[AUTO-MIGRATE] 自动迁移已禁用 (AUTO_MIGRATE=false)")
        print("[AUTO-MIGRATE] 自动迁移已禁用 (AUTO_MIGRATE=false)")
        return False

    issues = check_migration_needed()
    if not issues:
        logger.info("[AUTO-MIGRATE] ✅ 数据库结构完整，无需迁移")
        print("[AUTO-MIGRATE] ✅ 数据库结构完整，无需迁移")
        return True

    print(f"[AUTO-MIGRATE] 检测到 {len(issues)} 个问题，开始自动迁移...")
    logger.info(f"[AUTO-MIGRATE] 检测到 {len(issues)} 个问题，开始自动迁移...")

    db = SessionLocal()
    try:
        with migration_lock(db):
            # 迁移 1: secret_keys 表
            if ("table", "secret_keys") in issues:
                print("[AUTO-MIGRATE] [1/3] 创建 secret_keys 表...")
                logger.info("[AUTO-MIGRATE] [1/3] 创建 secret_keys 表...")
                from app.auth.migrations.add_secret_keys_table import run_migration
                run_migration()
                print("[AUTO-MIGRATE] ✅ secret_keys 表创建完成")
                logger.info("[AUTO-MIGRATE] ✅ secret_keys 表创建完成")

            # 迁移 2: sessions 表
            if ("table", "sessions") in issues or ("column", "refresh_tokens.session_id") in issues:
                print("[AUTO-MIGRATE] [2/3] 创建 sessions 表...")
                logger.info("[AUTO-MIGRATE] [2/3] 创建 sessions 表...")
                from app.auth.migrations.migrate_to_sessions import run_migration
                run_migration()
                print("[AUTO-MIGRATE] ✅ sessions 表创建完成")
                logger.info("[AUTO-MIGRATE] ✅ sessions 表创建完成")

            # 迁移 3: refresh_tokens 追踪字段
            if ("column", "refresh_tokens.ip_address") in issues or ("column", "refresh_tokens.device_info") in issues:
                print("[AUTO-MIGRATE] [3/3] 添加 refresh_tokens 追踪字段...")
                logger.info("[AUTO-MIGRATE] [3/3] 添加 refresh_tokens 追踪字段...")
                from app.auth.migrations.add_refresh_token_tracking_fields import run_migration
                run_migration()
                print("[AUTO-MIGRATE] ✅ refresh_tokens 追踪字段添加完成")
                logger.info("[AUTO-MIGRATE] ✅ refresh_tokens 追踪字段添加完成")

        print("[AUTO-MIGRATE] 🎉 所有迁移完成！")
        logger.info("[AUTO-MIGRATE] 🎉 所有迁移完成！")
        return True

    except Exception as e:
        logger.error(f"[AUTO-MIGRATE] ❌ 迁移失败: {e}")
        print(f"[AUTO-MIGRATE] ❌ 迁移失败: {e}")
        print(f"[AUTO-MIGRATE] 应用将在降级模式下启动")
        logger.error(f"[AUTO-MIGRATE] 应用将在降级模式下启动")

        # ✅ 打印完整堆栈
        import traceback
        traceback.print_exc()

        return False
    finally:
        db.close()
