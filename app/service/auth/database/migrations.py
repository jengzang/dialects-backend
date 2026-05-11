from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy.engine import Engine

from app.common.path import USER_DATABASE_PATH
from app.service.auth.core.utils import normalize_email


USER_COLUMNS = [
    "id",
    "username",
    "email",
    "hashed_password",
    "role",
    "status",
    "is_verified",
    "created_at",
    "updated_at",
    "register_ip",
    "last_login",
    "last_login_ip",
    "login_count",
    "failed_attempts",
    "last_failed_login",
    "total_online_seconds",
    "current_session_started_at",
    "last_seen",
    "profile_picture",
]


def _resolve_db_path(db_path: str | Path | None = None) -> str:
    return str(db_path or USER_DATABASE_PATH)


def _get_sqlite_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(_resolve_db_path(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def migrate_users_email_nullable_if_needed(db_path: str | Path | None = None) -> bool:
    conn = _get_sqlite_connection(db_path)
    try:
        row = conn.execute("PRAGMA table_info(users)").fetchall()
        if not row:
            return False

        email_col = next((item for item in row if item[1] == "email"), None)
        if not email_col or email_col[3] == 0:
            return False

        print("[MIGRATE] users.email 仍为 NOT NULL，开始迁移为 nullable 投影字段")
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        conn.execute("ALTER TABLE users RENAME TO users_legacy_email_notnull")
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER NOT NULL PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                email VARCHAR(100),
                hashed_password VARCHAR(255) NOT NULL,
                role VARCHAR(20),
                status VARCHAR(20),
                is_verified BOOLEAN,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME,
                register_ip VARCHAR(45),
                last_login DATETIME,
                last_login_ip VARCHAR(45),
                login_count INTEGER,
                failed_attempts INTEGER,
                last_failed_login DATETIME,
                total_online_seconds INTEGER,
                current_session_started_at DATETIME,
                last_seen DATETIME,
                profile_picture VARCHAR(255)
            )
            """
        )
        conn.execute(
            f"INSERT INTO users ({', '.join(USER_COLUMNS)}) SELECT {', '.join(USER_COLUMNS)} FROM users_legacy_email_notnull"
        )
        conn.execute("DROP TABLE users_legacy_email_notnull")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_users_id ON users (id)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
        conn.commit()
        print("[MIGRATE] users.email 已迁移为 nullable")
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        conn.close()


def backfill_email_identities(db_path: str | Path | None = None) -> int:
    conn = _get_sqlite_connection(db_path)
    inserted = 0
    try:
        rows = conn.execute(
            "SELECT id, email, is_verified, created_at FROM users WHERE email IS NOT NULL AND TRIM(email) != ''"
        ).fetchall()
        for row in rows:
            normalized = normalize_email(row["email"])
            existing = conn.execute(
                "SELECT id FROM user_auth_identities WHERE user_id = ? AND provider = 'email'",
                (row["id"],),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE user_auth_identities
                    SET identifier_normalized = ?,
                        email = ?,
                        is_primary = 1,
                        is_verified = COALESCE(is_verified, ?),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (normalized, row["email"], int(bool(row["is_verified"])), existing[0]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO user_auth_identities (
                        user_id, provider, provider_subject, identifier_normalized, email,
                        display_name, is_verified, is_primary, created_at, updated_at, last_login_at
                    ) VALUES (?, 'email', NULL, ?, ?, ?, ?, 1, COALESCE(?, CURRENT_TIMESTAMP), CURRENT_TIMESTAMP, NULL)
                    """,
                    (
                        row["id"],
                        normalized,
                        row["email"],
                        row["email"],
                        int(bool(row["is_verified"])),
                        row["created_at"],
                    ),
                )
                inserted += 1

        conn.execute(
            """
            UPDATE users
            SET email = (
                SELECT uai.email
                FROM user_auth_identities uai
                WHERE uai.user_id = users.id AND uai.provider = 'email' AND uai.is_primary = 1
                LIMIT 1
            ),
            is_verified = COALESCE((
                SELECT uai.is_verified
                FROM user_auth_identities uai
                WHERE uai.user_id = users.id AND uai.provider = 'email' AND uai.is_primary = 1
                LIMIT 1
            ), users.is_verified)
            """
        )
        conn.commit()
        if inserted:
            print(f"[MIGRATE] 已回填 {inserted} 条 email identities")
        return inserted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def repair_user_foreign_key_references(db_path: str | Path | None = None) -> int:
    conn = _get_sqlite_connection(db_path)
    try:
        broken = conn.execute(
            "SELECT name FROM sqlite_master WHERE sql LIKE '%users_legacy_email_notnull%'"
        ).fetchall()
        if not broken:
            return 0

        conn.execute("PRAGMA writable_schema=ON")
        conn.execute(
            """
            UPDATE sqlite_master
            SET sql = REPLACE(sql, '"users_legacy_email_notnull"', 'users')
            WHERE sql LIKE '%users_legacy_email_notnull%'
            """
        )
        schema_version = conn.execute("PRAGMA schema_version").fetchone()[0]
        conn.execute(f"PRAGMA schema_version = {schema_version + 1}")
        conn.execute("PRAGMA writable_schema=OFF")
        conn.commit()
        print(f"[MIGRATE] 已修复 {len(broken)} 张表对 users_legacy_email_notnull 的外键引用")
        return len(broken)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_identity_profile_picture_column(db_path: str | Path | None = None) -> bool:
    conn = _get_sqlite_connection(db_path)
    try:
        columns = conn.execute("PRAGMA table_info(user_auth_identities)").fetchall()
        existing = {row[1] for row in columns}
        if "profile_picture" in existing:
            return False
        conn.execute("ALTER TABLE user_auth_identities ADD COLUMN profile_picture TEXT")
        conn.commit()
        print("[MIGRATE] 已为 user_auth_identities 补充 profile_picture 列")
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_auth_schema_migrations(engine: Engine, db_path: str | Path | None = None) -> None:
    # 先让 SQLAlchemy 建新表，再处理旧表重建/回填
    from app.service.auth.database.models import Base

    Base.metadata.create_all(bind=engine)
    migrate_users_email_nullable_if_needed(db_path)
    repair_user_foreign_key_references(db_path)
    Base.metadata.create_all(bind=engine)
    ensure_identity_profile_picture_column(db_path)
    backfill_email_identities(db_path)
