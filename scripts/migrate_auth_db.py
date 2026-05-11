from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine

from app.service.auth.database.migrations import run_auth_schema_migrations


def inspect_db(db_path: Path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        tables = [
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        email_col = next(
            row for row in cur.execute("PRAGMA table_info(users)").fetchall() if row[1] == "email"
        )
        broken_fk_refs = cur.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE sql LIKE '%users_legacy_email_notnull%'"
        ).fetchone()[0]
        identity_count = cur.execute("SELECT COUNT(*) FROM user_auth_identities").fetchone()[0]
        token_count = cur.execute("SELECT COUNT(*) FROM auth_action_tokens").fetchone()[0]
        return {
            "tables": tables,
            "email_nullable": email_col[3] == 0,
            "broken_fk_refs": broken_fk_refs,
            "identity_count": identity_count,
            "token_count": token_count,
        }
    finally:
        conn.close()


def backup_db(db_path: Path) -> Path:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.with_name(f"{db_path.name}.bak_{timestamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def migrate_db(db_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    run_auth_schema_migrations(engine, db_path=str(db_path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate auth.db for multi-identity auth support")
    parser.add_argument("--db-path", default="data/auth.db", help="Path to auth SQLite database")
    parser.add_argument("--check-only", action="store_true", help="Only inspect database state")
    parser.add_argument("--skip-backup", action="store_true", help="Do not create backup before migration")
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    print(f"[AUTH-DB] target={db_path}")

    if args.check_only:
        info = inspect_db(db_path)
        print(f"[AUTH-DB] tables={info['tables']}")
        print(f"[AUTH-DB] email_nullable={info['email_nullable']}")
        print(f"[AUTH-DB] broken_fk_refs={info['broken_fk_refs']}")
        print(f"[AUTH-DB] identity_count={info['identity_count']}")
        print(f"[AUTH-DB] token_count={info['token_count']}")
        return 0

    if not args.skip_backup:
        backup_path = backup_db(db_path)
        print(f"[AUTH-DB] backup={backup_path}")

    migrate_db(db_path)

    info = inspect_db(db_path)
    print(f"[AUTH-DB] migrated email_nullable={info['email_nullable']}")
    print(f"[AUTH-DB] broken_fk_refs={info['broken_fk_refs']}")
    print(f"[AUTH-DB] identity_count={info['identity_count']}")
    print(f"[AUTH-DB] token_count={info['token_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
