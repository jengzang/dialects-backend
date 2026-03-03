"""
Database Migration Script for Refresh Tokens
Creates the refresh_tokens table if it doesn't exist.

Run this script once to add refresh token support to existing database.
"""

import sqlite3
import sys
from app.common.path import USER_DATABASE_PATH

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')


def migrate():
    """Create refresh_tokens table"""
    conn = sqlite3.connect(USER_DATABASE_PATH)
    cursor = conn.cursor()

    # Check if table already exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='refresh_tokens'
    """)

    if cursor.fetchone():
        print("✓ refresh_tokens table already exists, skipping migration")
        conn.close()
        return

    # Create refresh_tokens table
    cursor.execute("""
        CREATE TABLE refresh_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token VARCHAR UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            revoked BOOLEAN DEFAULT 0,
            replaced_by VARCHAR,
            device_info VARCHAR,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Create indexes for better performance
    cursor.execute("""
        CREATE INDEX idx_refresh_tokens_token ON refresh_tokens(token)
    """)

    cursor.execute("""
        CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id)
    """)

    cursor.execute("""
        CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at)
    """)

    conn.commit()
    conn.close()

    print("✓ Successfully created refresh_tokens table and indexes")


if __name__ == "__main__":
    print("Running database migration for refresh tokens...")
    migrate()
    print("Migration completed!")
