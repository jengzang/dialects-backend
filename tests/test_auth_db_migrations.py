from pathlib import Path
import sqlite3
import tempfile
import unittest

from sqlalchemy import create_engine

from app.service.auth.database.migrations import run_auth_schema_migrations


class AuthDbMigrationTests(unittest.TestCase):
    def test_migration_adds_missing_auth_action_token_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "auth.db"
            conn = sqlite3.connect(db_path)
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
                """
                CREATE TABLE user_auth_identities (
                    id INTEGER NOT NULL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    provider VARCHAR(32) NOT NULL,
                    provider_subject VARCHAR(255),
                    identifier_normalized VARCHAR(255),
                    email VARCHAR(255),
                    display_name VARCHAR(255),
                    profile_picture TEXT,
                    is_verified BOOLEAN,
                    is_primary BOOLEAN,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME,
                    last_login_at DATETIME
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE auth_action_tokens (
                    id INTEGER NOT NULL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    identity_id INTEGER,
                    action VARCHAR(32) NOT NULL,
                    token_hash VARCHAR(64) NOT NULL,
                    requested_ip VARCHAR(45),
                    expires_at DATETIME NOT NULL,
                    consumed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    target_email TEXT,
                    verified_at DATETIME
                )
                """
            )
            conn.commit()
            conn.close()

            engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, pool_pre_ping=True)
            run_auth_schema_migrations(engine, db_path=str(db_path))

            conn = sqlite3.connect(db_path)
            columns = {row[1]: row for row in conn.execute("PRAGMA table_info(auth_action_tokens)").fetchall()}
            conn.close()

            self.assertIn("metadata_json", columns)
            self.assertIn("target_email", columns)
            self.assertIn("verified_at", columns)
            self.assertEqual(columns["user_id"][3], 0)


if __name__ == "__main__":
    unittest.main()
