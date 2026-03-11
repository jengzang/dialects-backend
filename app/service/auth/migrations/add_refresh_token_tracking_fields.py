"""
迁移: 为refresh_tokens表添加追踪字段
运行: python -m app.auth.migrations.add_refresh_token_tracking_fields
"""
from sqlalchemy import text, inspect
from app.service.auth.database import engine, SessionLocal


def run_migration():
    """为refresh_tokens表添加ip_address和device_info列（幂等性）"""
    print("[MIGRATION] Adding tracking fields to refresh_tokens table...")

    db = SessionLocal()
    inspector = inspect(engine)

    try:
        # 设置更长的busy timeout（30秒）以处理多worker竞争
        db.execute(text("PRAGMA busy_timeout = 30000"))
        db.commit()

        # 检查refresh_tokens表是否存在
        if 'refresh_tokens' not in inspector.get_table_names():
            print("[ERROR] refresh_tokens table does not exist")
            return

        # 检查列是否已存在
        columns = [col['name'] for col in inspector.get_columns('refresh_tokens')]

        # 添加 ip_address 列
        if 'ip_address' not in columns:
            print("[1/2] Adding ip_address column...")
            db.execute(text("""
                ALTER TABLE refresh_tokens
                ADD COLUMN ip_address VARCHAR(45)
            """))
            db.commit()
            print("[OK] ip_address column added")
        else:
            print("[1/2] [SKIP] ip_address column already exists")

        # 添加 device_info 列
        if 'device_info' not in columns:
            print("[2/2] Adding device_info column...")
            db.execute(text("""
                ALTER TABLE refresh_tokens
                ADD COLUMN device_info TEXT
            """))
            db.commit()
            print("[OK] device_info column added")
        else:
            print("[2/2] [SKIP] device_info column already exists")

        print("[MIGRATION] Complete!")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
