"""
可选迁移: 为现有 refresh_tokens 回填 IP 地址
从 sessions 表中获取 IP 信息
运行: python -m app.auth.migrations.backfill_token_ip
"""
from sqlalchemy import text
from app.service.auth.database import SessionLocal


def run_migration():
    """从 sessions 表回填 refresh_tokens 的 IP 地址"""
    print("[MIGRATION] Backfilling IP addresses for existing tokens...")

    db = SessionLocal()

    try:
        # 从 sessions 表回填 IP 到 refresh_tokens
        result = db.execute(text("""
            UPDATE refresh_tokens
            SET ip_address = (
                SELECT s.current_ip
                FROM sessions s
                WHERE s.id = refresh_tokens.session_id
            )
            WHERE refresh_tokens.ip_address IS NULL
              AND refresh_tokens.session_id IS NOT NULL
        """))

        db.commit()
        updated_count = result.rowcount
        print(f"[OK] Updated {updated_count} tokens with IP addresses")

        print("[MIGRATION] Complete!")

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
