from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

from app.service.auth.database.migrate_api_usage_summary import (
    audit_api_usage_summary,
    migrate_api_usage_summary,
)
from app.service.logging.utils.usage_paths import (
    normalize_auth_usage_path,
    normalize_auth_usage_path_for_migration,
    should_record_auth_usage,
)


def _create_summary_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE api_usage_summary (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                path TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                last_updated DATETIME,
                total_duration DECIMAL(10, 2) DEFAULT 0.00,
                total_upload DECIMAL(10, 2) DEFAULT 0.00,
                total_download DECIMAL(10, 2) DEFAULT 0.00
            )
            """
        )
        conn.execute(
            "CREATE INDEX ix_api_usage_summary_user_id ON api_usage_summary(user_id)"
        )
        conn.executemany(
            """
            INSERT INTO api_usage_summary (
                user_id, path, count, last_updated, total_duration, total_upload, total_download
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    "/api/villages/village/complete/282728",
                    2,
                    "2026-03-26 10:00:00",
                    "12.50",
                    "1.50",
                    "2.50",
                ),
                (
                    1,
                    "/api/villages/village/complete/281635",
                    3,
                    "2026-03-26 11:00:00",
                    "4.25",
                    "0.50",
                    "1.00",
                ),
                (
                    2,
                    "/api/search_chars/",
                    7,
                    "2026-03-26 09:00:00",
                    "20.00",
                    "3.00",
                    "5.00",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_normalize_auth_usage_path_examples():
    assert (
        normalize_auth_usage_path("/api/villages/village/complete/282728")
        == "/api/villages/village/complete/{village_id}"
    )
    assert (
        normalize_auth_usage_path("/api/villages/spatial/integration/by-character/gao")
        == "/api/villages/spatial/integration/by-character/{character}"
    )
    assert (
        normalize_auth_usage_path("/sql/distinct/query/dialects/abbr")
        == "/sql/distinct/query/dialects/abbr"
    )
    assert (
        normalize_auth_usage_path_for_migration("/sql/distinct/query/dialects/abbr")
        == "/sql/distinct/{db_key}/{table_name}/{column}"
    )
    assert normalize_auth_usage_path("/api/search_chars/") == "/api/search_chars/"
    assert (
        normalize_auth_usage_path("/api/tools/check/download/abc")
        == "/api/tools/check/download/abc"
    )
    assert (
        normalize_auth_usage_path_for_migration("/api/tools/check/download/abc")
        == "/api/tools/check/download/{task_id}"
    )


def test_should_record_auth_usage_uses_exact_and_wildcard_rules():
    assert should_record_auth_usage("/api/phonology") is True
    assert should_record_auth_usage("/api/phonology_matrix") is True
    assert should_record_auth_usage("/api/phonology_classification_matrix") is True
    assert should_record_auth_usage("/api/get_coordinates") is True
    assert should_record_auth_usage("/api/get_coordinates/extra") is False
    assert should_record_auth_usage("/api/search_chars/") is True
    assert should_record_auth_usage("/api/search_chars") is False
    assert should_record_auth_usage("/api/compare/chars") is True
    assert should_record_auth_usage("/api/compare/ZhongGu") is True
    assert should_record_auth_usage("/api/custom_regions") is True
    assert should_record_auth_usage("/user/custom/all") is True
    assert should_record_auth_usage("/api/villages/village/complete/282728") is True
    assert should_record_auth_usage("/api/tools/check/run") is True
    assert should_record_auth_usage("/sql/query") is True
    assert should_record_auth_usage("/sql/query/columns") is False
    assert should_record_auth_usage("/sql/distinct/query/dialects/abbr") is False
    assert should_record_auth_usage("/sql/distinct-query") is True
    assert should_record_auth_usage("/sql/mutate") is True
    assert should_record_auth_usage("/sql/tree/lazy") is True
    assert should_record_auth_usage("/sql/query/count") is False
    assert should_record_auth_usage("/sql/querying") is False
    assert should_record_auth_usage("/foo/sql/query/bar") is False
    assert should_record_auth_usage("/api/tools/check/download/abc") is False
    assert should_record_auth_usage("/api/tools/praat/jobs/progress/123") is False
    assert should_record_auth_usage("/emp/lang2sql") is False


def test_migrate_api_usage_summary_preserves_totals_and_normalizes_paths(tmp_path):
    db_path = tmp_path / "auth.db"
    _create_summary_db(db_path)

    audit = audit_api_usage_summary(db_path)
    assert audit.affected_rows == 2
    assert audit.totals_before == audit.totals_after

    result = migrate_api_usage_summary(db_path)
    assert result["changed"] is True
    assert result["backup_path"] is not None
    assert Path(result["backup_path"]).exists()

    post_audit = audit_api_usage_summary(db_path)
    assert post_audit.affected_rows == 0
    assert post_audit.totals_before == audit.totals_before

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT user_id, path, count, last_updated, total_duration, total_upload, total_download
            FROM api_usage_summary
            ORDER BY user_id, path
            """
        ).fetchall()
        assert rows == [
            (
                1,
                "/api/villages/village/complete/{village_id}",
                5,
                "2026-03-26 11:00:00",
                16.75,
                2,
                3.5,
            ),
            (
                2,
                "/api/search_chars/",
                7,
                "2026-03-26 09:00:00",
                20,
                3,
                5,
            ),
        ]

        total_count, total_duration, total_upload, total_download = conn.execute(
            """
            SELECT
                SUM(count),
                SUM(total_duration),
                SUM(total_upload),
                SUM(total_download)
            FROM api_usage_summary
            """
        ).fetchone()
        assert total_count == 12
        assert Decimal(str(total_duration)) == Decimal("36.75")
        assert Decimal(str(total_upload)) == Decimal("5.0")
        assert Decimal(str(total_download)) == Decimal("8.5")
    finally:
        conn.close()
