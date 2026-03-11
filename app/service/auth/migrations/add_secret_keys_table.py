"""
迁移: 添加secret_keys表
运行: python -m app.auth.migrations.add_secret_keys_table
"""
from sqlalchemy import inspect, text
from app.service.auth.database import engine, SessionLocal
from app.service.auth.models import Base, SecretKey
from app.service.auth.key_manager import _generate_new_secret_key


def run_migration():
    """创建 secret_keys 表（幂等性）"""
    print("[MIGRATION] ========== add_secret_keys_table ==========")
    print("[MIGRATION] Checking if secret_keys table exists...")

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"[MIGRATION] Current tables: {tables}")

    if 'secret_keys' in tables:
        print("[MIGRATION] ⚠️  secret_keys table already exists")

        # 检查是否有密钥
        db = SessionLocal()
        try:
            # 设置busy timeout
            db.execute(text("PRAGMA busy_timeout = 30000"))
            db.commit()

            existing_keys = db.query(SecretKey).all()
            print(f"[MIGRATION] Found {len(existing_keys)} existing keys")

            if len(existing_keys) == 0:
                print("[MIGRATION] Table is empty, generating initial key...")
                key = _generate_new_secret_key(db)
                print(f"[MIGRATION] ✅ Initial key generated with ID: {key.id}")
            else:
                print("[MIGRATION] Keys already exist, skipping generation")
                for key in existing_keys:
                    print(f"  - Key ID {key.id}: active={key.active}, expires_at={key.expires_at}")
        except Exception as e:
            print(f"[MIGRATION] ❌ Error checking/generating keys: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            db.close()
        return

    # 创建表
    print("[MIGRATION] Creating secret_keys table...")
    Base.metadata.create_all(bind=engine, tables=[SecretKey.__table__])
    print("[MIGRATION] ✅ Table created")

    # 生成首个SECRET_KEY
    print("[MIGRATION] Generating initial SECRET_KEY...")
    db = SessionLocal()
    try:
        # 设置busy timeout
        db.execute(text("PRAGMA busy_timeout = 30000"))
        db.commit()

        key = _generate_new_secret_key(db)
        print(f"[MIGRATION] ✅ Initial SECRET_KEY generated with ID: {key.id}")
    except Exception as e:
        print(f"[MIGRATION] ❌ Failed to generate initial key: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

    print("[MIGRATION] ========== Migration complete ==========")


if __name__ == "__main__":
    run_migration()
