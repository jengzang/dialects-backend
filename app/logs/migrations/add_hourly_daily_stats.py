"""
数据库迁移：添加 API 小时级和每日统计表

创建两张新表：
1. api_usage_hourly - 小时级总调用统计（不区分API路径）
2. api_usage_daily - 每日每API调用统计
"""

from datetime import datetime


def migrate_hourly_daily_stats(db):
    """创建 api_usage_hourly 和 api_usage_daily 表"""
    cursor = db.cursor()

    # 检查 api_usage_hourly 表是否存在
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='api_usage_hourly'"
    )
    if not cursor.fetchone():
        # 创建 api_usage_hourly 表
        cursor.execute("""
            CREATE TABLE api_usage_hourly (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour DATETIME NOT NULL,
                total_calls INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE UNIQUE INDEX idx_hourly_hour ON api_usage_hourly(hour)"
        )
        print("[Migration] Created api_usage_hourly table")
    else:
        print("[Migration] api_usage_hourly table already exists")

    # 检查 api_usage_daily 表是否存在
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='api_usage_daily'"
    )
    if not cursor.fetchone():
        # 创建 api_usage_daily 表
        cursor.execute("""
            CREATE TABLE api_usage_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                path VARCHAR(255) NOT NULL,
                call_count INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE UNIQUE INDEX idx_daily_date_path ON api_usage_daily(date, path)"
        )
        cursor.execute("CREATE INDEX idx_daily_date ON api_usage_daily(date)")
        cursor.execute("CREATE INDEX idx_daily_path ON api_usage_daily(path)")
        print("[Migration] Created api_usage_daily table")
    else:
        print("[Migration] api_usage_daily table already exists")

    db.commit()
    print("[Migration] Hourly and daily stats migration completed")
