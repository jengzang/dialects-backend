"""
迁移: 添加sessions表并迁移现有数据
运行: python -m app.auth.migrations.migrate_to_sessions
"""

import json
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from app.auth.database import engine, SessionLocal
from app.auth.models import Base, Session, RefreshToken, User
from app.common.config import REFRESH_TOKEN_EXPIRE_DAYS


def run_migration():
    """创建 sessions 表并迁移数据（幂等性）"""
    print("[MIGRATION] Starting session table migration...")

    db = SessionLocal()
    from sqlalchemy import inspect as sqlalchemy_inspect
    inspector = sqlalchemy_inspect(engine)

    try:
        # 设置更长的busy timeout（30秒）以处理多worker竞争
        db.execute(text("PRAGMA busy_timeout = 30000"))
        db.commit()

        # Step 1: 创建sessions表
        if 'sessions' not in inspector.get_table_names():
            print("[1/4] Creating sessions table...")
            Base.metadata.create_all(bind=engine, tables=[Session.__table__])
            print("✅ Sessions table created")
        else:
            print("[1/4] ⚠️  Sessions table already exists, skipping")

        # Step 2: 为每个有活跃token的用户创建legacy session（检查是否已迁移）
        from app.auth.models import Session as SessionModel
        existing_sessions = db.query(SessionModel).count()

        if existing_sessions == 0:
            print("[2/4] Creating legacy sessions for existing users...")
            # 查询有活跃token的用户
            users_with_tokens = db.execute(text("""
                SELECT DISTINCT u.id, u.username, r.device_info, r.created_at, r.expires_at
                FROM users u
                JOIN refresh_tokens r ON u.id = r.user_id
                WHERE r.revoked = 0 AND r.expires_at > datetime('now')
                ORDER BY u.id, r.created_at DESC
            """)).fetchall()

            session_map = {}  # user_id -> session_id (DB primary key)

            for row in users_with_tokens:
                user_id, username, device_info, created_at, expires_at = row

                if user_id not in session_map:
                    session_id = f"legacy-{user_id}-{uuid.uuid4().hex[:8]}"

                    new_session = Session(
                        session_id=session_id,
                        user_id=user_id,
                        username=username,
                        created_at=datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at,
                        expires_at=datetime.fromisoformat(expires_at) if isinstance(expires_at, str) else expires_at,
                        first_ip="0.0.0.0",  # 历史数据无IP记录
                        current_ip="0.0.0.0",
                        device_info=device_info or "Unknown",
                        first_device_info=device_info or "Unknown",
                        ip_history=json.dumps([]),
                        refresh_count=0
                    )
                    db.add(new_session)

                    # 重试机制：处理database is locked错误
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            db.flush()  # 获取session.id
                            break
                        except Exception as flush_error:
                            if "database is locked" in str(flush_error).lower() and attempt < max_retries - 1:
                                import time
                                time.sleep(1)  # 等待1秒后重试
                                continue
                            raise

                    session_map[user_id] = new_session.id

            db.commit()
            print(f"✅ Created {len(session_map)} legacy sessions")
        else:
            print(f"[2/4] ⚠️  已存在 {existing_sessions} 个会话，跳过迁移")
            session_map = {}  # 空字典，跳过后续关联

        # Step 3: 为refresh_tokens表添加session_id列（如果不存在）
        if 'refresh_tokens' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('refresh_tokens')]
            if 'session_id' not in columns:
                print("[3/4] Adding session_id column to refresh_tokens...")
                db.execute(text("""
                    ALTER TABLE refresh_tokens
                    ADD COLUMN session_id INTEGER
                    REFERENCES sessions(id) ON DELETE CASCADE
                """))
                db.commit()
                print("✅ Column added")
            else:
                print("[3/4] ⚠️  Column session_id already exists, skipping")

        # Step 4: 关联refresh_tokens到sessions
        if session_map:  # 只有创建了新session时才关联
            print("[4/4] Linking refresh tokens to sessions...")
            for user_id, session_id in session_map.items():
                db.execute(text("""
                    UPDATE refresh_tokens
                    SET session_id = :session_id
                    WHERE user_id = :user_id AND session_id IS NULL
                """), {"session_id": session_id, "user_id": user_id})
            db.commit()
            print("✅ Refresh tokens linked")
        else:
            print("[4/4] ⚠️  跳过token关联（没有新session）")

        print("[MIGRATION] Complete! ✅")
        print("\n⚠️  IMPORTANT: Keep old User table fields for 30 days as fallback")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
