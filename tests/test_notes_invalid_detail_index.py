import sqlite3
import subprocess
import sys

from app.sql import index_manager


def test_invalid_detail_index_migration_is_idempotent_and_covers_count(tmp_path):
    db_path = tmp_path / "dialects_user.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE notes (註釋 TEXT)")
        conn.executemany(
            "INSERT INTO notes(註釋) VALUES (?)",
            [("有效",), (None,), ("   ",), ("_",), (" - ",)],
        )

    index_manager.ensure_notes_invalid_detail_index(db_path)
    subprocess.run(
        [sys.executable, "-m", "app.sql.index_manager", "notes-invalid-detail", str(db_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    with sqlite3.connect(db_path) as conn:
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='notes'"
        ).fetchall()
        plan = conn.execute(
            "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM notes "
            "WHERE TRIM(COALESCE(註釋, '')) IN ('', '_', '-')"
        ).fetchall()
        count = conn.execute(
            "SELECT COUNT(*) FROM notes "
            "WHERE TRIM(COALESCE(註釋, '')) IN ('', '_', '-')"
        ).fetchone()[0]

    assert indexes == [("idx_notes_invalid_detail",)]
    assert any("COVERING INDEX idx_notes_invalid_detail" in row[3] for row in plan)
    assert count == 4
