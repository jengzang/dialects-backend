import sqlite3

from app.common.path import (
    CHARACTERS_DB_PATH,
    DIALECTS_DB_ADMIN,
    DIALECTS_DB_USER,
    LOGS_DATABASE_PATH,
    QUERY_DB_ADMIN,
    QUERY_DB_USER,
)
from app.redis_client import close_redis
from app.sql.db_pool import close_all_pools, get_db_pool


def initialize_db_pools() -> None:
    print("=" * 60)
    print("[DB] Initializing database pools...")
    try:
        get_db_pool(QUERY_DB_ADMIN, pool_size=5)
        get_db_pool(QUERY_DB_USER, pool_size=5)
        get_db_pool(DIALECTS_DB_ADMIN, pool_size=10)
        get_db_pool(DIALECTS_DB_USER, pool_size=10)
        get_db_pool(CHARACTERS_DB_PATH, pool_size=5)
        print("[OK] Database pools initialized")
    except Exception as exc:
        print(f"[WARN] Database pool initialization failed: {exc}")
    print("=" * 60)


def migrate_user_region_tables() -> None:
    from app.service.user.core.database import migrate_user_regions_table

    print("=" * 60)
    print("[DB] Checking supplements.db schema...")
    try:
        migrate_user_regions_table()
        print("[OK] supplements.db schema check completed")
    except Exception as exc:
        print(f"[WARN] supplements.db migration failed: {exc}")
    print("=" * 60)


def migrate_logs_database() -> None:
    from app.service.logging.core.database import (
        migrate_api_diagnostic_events,
        migrate_hourly_daily_stats,
    )

    print("=" * 60)
    print("[DB] Checking logs.db analytics tables...")
    logs_db = None
    try:
        logs_db = sqlite3.connect(LOGS_DATABASE_PATH)
        migrate_hourly_daily_stats(logs_db)
        migrate_api_diagnostic_events()
        print("[OK] logs.db schema check completed")
    except Exception as exc:
        print(f"[WARN] logs.db migration failed: {exc}")
    finally:
        if logs_db is not None:
            logs_db.close()
    print("=" * 60)


def cleanup_old_temp_files() -> None:
    from app.tools.file_manager import file_manager

    print("=" * 60)
    print("[CLEANUP] Removing old temp files (older than 12h)...")
    try:
        deleted_count = file_manager.cleanup_old_files(max_age_hours=12)
        print(f"[OK] Removed {deleted_count} expired task directories")
    except Exception as exc:
        print(f"[WARN] Temp file cleanup failed: {exc}")
    print("=" * 60)


def warm_dialect_cache() -> None:
    from app.service.geo.match_input_tip import _load_dialect_cache

    print("=" * 60)
    print("[CACHE] Warming dialect caches...")
    try:
        _load_dialect_cache(QUERY_DB_ADMIN, filter_valid_abbrs_only=True)
        _load_dialect_cache(QUERY_DB_USER, filter_valid_abbrs_only=True)
        _load_dialect_cache(QUERY_DB_ADMIN, filter_valid_abbrs_only=False)
        _load_dialect_cache(QUERY_DB_USER, filter_valid_abbrs_only=False)
        print("[OK] Dialect cache warmup completed")
    except Exception as exc:
        print(f"[WARN] Dialect cache warmup failed: {exc}")
    print("=" * 60)


def run_process_startup() -> None:
    initialize_db_pools()
    migrate_user_region_tables()
    migrate_logs_database()
    cleanup_old_temp_files()
    warm_dialect_cache()


async def shutdown_process_resources() -> None:
    try:
        await close_redis()
    finally:
        print("[DB] Closing database pools...")
        close_all_pools()
        print("[OK] Database pools closed")
