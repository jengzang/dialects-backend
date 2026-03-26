"""One-off migration tool for normalizing auth.db api_usage_summary paths."""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from app.common.path import USER_DATABASE_PATH
from app.service.logging.utils.usage_paths import (
    auth_usage_path_needs_migration,
    normalize_auth_usage_path_for_migration,
)


SUMMARY_TABLE = "api_usage_summary"
TEMP_TABLE = "api_usage_summary_migrated_tmp"


@dataclass(frozen=True)
class SummaryTotals:
    count: int = 0
    total_duration: Decimal = Decimal("0")
    total_upload: Decimal = Decimal("0")
    total_download: Decimal = Decimal("0")


@dataclass(frozen=True)
class SummaryAuditResult:
    total_rows: int
    distinct_paths: int
    affected_rows: int
    affected_paths: tuple[str, ...]
    grouped_rows: tuple[tuple[int | None, str, int, str | None, Decimal, Decimal, Decimal], ...]
    totals_before: SummaryTotals
    totals_after: SummaryTotals
    user_totals_before: dict[int | None, SummaryTotals]
    user_totals_after: dict[int | None, SummaryTotals]


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _safe_int(value) -> int:
    if value is None:
        return 0
    return int(value)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _fetch_summary_rows(conn: sqlite3.Connection, table_name: str = SUMMARY_TABLE) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    if not _table_exists(conn, table_name):
        raise RuntimeError(f"Table '{table_name}' does not exist")
    return list(conn.execute(f"SELECT * FROM {table_name}"))


def _sum_rows(rows: Iterable[sqlite3.Row | dict]) -> tuple[SummaryTotals, dict[int | None, SummaryTotals]]:
    overall = defaultdict(Decimal)
    overall["count"] = Decimal("0")
    per_user: dict[int | None, defaultdict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        user_id = row["user_id"]
        count = Decimal(_safe_int(row["count"]))
        total_duration = _decimal(row["total_duration"])
        total_upload = _decimal(row["total_upload"])
        total_download = _decimal(row["total_download"])

        overall["count"] += count
        overall["total_duration"] += total_duration
        overall["total_upload"] += total_upload
        overall["total_download"] += total_download

        per_user[user_id]["count"] += count
        per_user[user_id]["total_duration"] += total_duration
        per_user[user_id]["total_upload"] += total_upload
        per_user[user_id]["total_download"] += total_download

    totals = SummaryTotals(
        count=int(overall["count"]),
        total_duration=overall["total_duration"],
        total_upload=overall["total_upload"],
        total_download=overall["total_download"],
    )
    user_totals = {
        user_id: SummaryTotals(
            count=int(values["count"]),
            total_duration=values["total_duration"],
            total_upload=values["total_upload"],
            total_download=values["total_download"],
        )
        for user_id, values in per_user.items()
    }
    return totals, user_totals


def _group_rows(rows: Iterable[sqlite3.Row]) -> tuple[
    tuple[tuple[int | None, str, int, str | None, Decimal, Decimal, Decimal], ...],
    tuple[str, ...],
    int,
]:
    grouped: dict[tuple[int | None, str], dict[str, object]] = {}
    affected_paths: set[str] = set()
    affected_rows = 0

    for row in rows:
        original_path = row["path"]
        normalized_path = normalize_auth_usage_path_for_migration(original_path)
        if original_path != normalized_path:
            affected_rows += 1
            affected_paths.add(original_path)

        key = (row["user_id"], normalized_path)
        current = grouped.setdefault(
            key,
            {
                "count": 0,
                "last_updated": None,
                "total_duration": Decimal("0"),
                "total_upload": Decimal("0"),
                "total_download": Decimal("0"),
            },
        )
        current["count"] += _safe_int(row["count"])
        current["total_duration"] += _decimal(row["total_duration"])
        current["total_upload"] += _decimal(row["total_upload"])
        current["total_download"] += _decimal(row["total_download"])

        last_updated = row["last_updated"]
        if last_updated is not None and (
            current["last_updated"] is None or str(last_updated) > str(current["last_updated"])
        ):
            current["last_updated"] = last_updated

    grouped_rows = tuple(
        sorted(
            (
                (
                    user_id,
                    path,
                    int(values["count"]),
                    values["last_updated"],
                    values["total_duration"],
                    values["total_upload"],
                    values["total_download"],
                )
                for (user_id, path), values in grouped.items()
            ),
            key=lambda item: ((item[0] is None), item[0], item[1]),
        )
    )
    return grouped_rows, tuple(sorted(affected_paths)), affected_rows


def audit_api_usage_summary(db_path: str | Path = USER_DATABASE_PATH) -> SummaryAuditResult:
    db_path = Path(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = _fetch_summary_rows(conn)
    finally:
        conn.close()

    totals_before, user_totals_before = _sum_rows(rows)
    grouped_rows, affected_paths, affected_rows = _group_rows(rows)

    normalized_dict_rows = [
        {
            "user_id": row[0],
            "path": row[1],
            "count": row[2],
            "last_updated": row[3],
            "total_duration": row[4],
            "total_upload": row[5],
            "total_download": row[6],
        }
        for row in grouped_rows
    ]
    totals_after, user_totals_after = _sum_rows(normalized_dict_rows)

    return SummaryAuditResult(
        total_rows=len(rows),
        distinct_paths=len({row["path"] for row in rows}),
        affected_rows=affected_rows,
        affected_paths=affected_paths,
        grouped_rows=grouped_rows,
        totals_before=totals_before,
        totals_after=totals_after,
        user_totals_before=user_totals_before,
        user_totals_after=user_totals_after,
    )


def _build_backup_path(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return db_path.with_name(f"{db_path.stem}.bak.api_usage_summary.{timestamp}{db_path.suffix}")


def backup_database(db_path: str | Path) -> Path:
    db_path = Path(db_path)
    backup_path = _build_backup_path(db_path)

    source = sqlite3.connect(str(db_path))
    destination = sqlite3.connect(str(backup_path))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    return backup_path


def _get_create_table_sql(conn: sqlite3.Connection, table_name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if row is None or row[0] is None:
        raise RuntimeError(f"Cannot find CREATE TABLE statement for '{table_name}'")
    return row[0]


def _get_index_sql(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL
        ORDER BY name
        """,
        (table_name,),
    ).fetchall()
    return [row[0] for row in rows if row[0]]


def _replace_table_name(create_sql: str, source_name: str, target_name: str) -> str:
    candidates = [
        f"CREATE TABLE {source_name}",
        f'CREATE TABLE "{source_name}"',
        f"CREATE TABLE '{source_name}'",
    ]
    for prefix in candidates:
        if create_sql.startswith(prefix):
            return create_sql.replace(prefix, f"CREATE TABLE {target_name}", 1)
    raise RuntimeError(f"Unsupported CREATE TABLE statement: {create_sql}")


def _assert_totals_match(before: SummaryTotals, after: SummaryTotals) -> None:
    if before != after:
        raise RuntimeError(f"Overall totals mismatch: before={before}, after={after}")


def _assert_user_totals_match(
    before: dict[int | None, SummaryTotals],
    after: dict[int | None, SummaryTotals],
) -> None:
    if before.keys() != after.keys():
        raise RuntimeError("User set changed during migration")
    for user_id in before:
        if before[user_id] != after[user_id]:
            raise RuntimeError(
                f"User totals mismatch for user_id={user_id}: before={before[user_id]}, after={after[user_id]}"
            )


def _insert_grouped_rows(
    conn: sqlite3.Connection,
    grouped_rows: tuple[tuple[int | None, str, int, str | None, Decimal, Decimal, Decimal], ...],
) -> None:
    conn.executemany(
        f"""
        INSERT INTO {TEMP_TABLE} (
            user_id, path, count, last_updated, total_duration, total_upload, total_download
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                user_id,
                path,
                count,
                last_updated,
                str(total_duration),
                str(total_upload),
                str(total_download),
            )
            for user_id, path, count, last_updated, total_duration, total_upload, total_download in grouped_rows
        ],
    )


def migrate_api_usage_summary(db_path: str | Path = USER_DATABASE_PATH) -> dict[str, object]:
    db_path = Path(db_path)
    audit = audit_api_usage_summary(db_path)
    if audit.affected_rows == 0:
        return {
            "changed": False,
            "backup_path": None,
            "affected_rows": 0,
            "final_rows": audit.total_rows,
        }

    backup_path = backup_database(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if _table_exists(conn, TEMP_TABLE):
            raise RuntimeError(f"Temporary table '{TEMP_TABLE}' already exists; aborting for safety")

        create_sql = _get_create_table_sql(conn, SUMMARY_TABLE)
        index_sql = _get_index_sql(conn, SUMMARY_TABLE)

        conn.execute("BEGIN IMMEDIATE")
        conn.execute(_replace_table_name(create_sql, SUMMARY_TABLE, TEMP_TABLE))
        _insert_grouped_rows(conn, audit.grouped_rows)

        migrated_rows = _fetch_summary_rows(conn, TEMP_TABLE)
        totals_after, user_totals_after = _sum_rows(migrated_rows)
        _assert_totals_match(audit.totals_before, totals_after)
        _assert_user_totals_match(audit.user_totals_before, user_totals_after)

        remaining_dynamic = sum(
            1 for row in migrated_rows if auth_usage_path_needs_migration(row["path"])
        )
        if remaining_dynamic != 0:
            raise RuntimeError(
                f"Migration left {remaining_dynamic} rows that still require normalization"
            )

        conn.execute(f"DROP TABLE {SUMMARY_TABLE}")
        conn.execute(f"ALTER TABLE {TEMP_TABLE} RENAME TO {SUMMARY_TABLE}")
        for sql in index_sql:
            conn.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "changed": True,
        "backup_path": str(backup_path),
        "affected_rows": audit.affected_rows,
        "final_rows": len(audit.grouped_rows),
    }


def _format_totals(label: str, totals: SummaryTotals) -> str:
    return (
        f"{label}: count={totals.count}, "
        f"duration={totals.total_duration}, "
        f"upload={totals.total_upload}, "
        f"download={totals.total_download}"
    )


def print_audit_report(audit: SummaryAuditResult) -> None:
    print(f"Rows: {audit.total_rows}")
    print(f"Distinct paths: {audit.distinct_paths}")
    print(f"Affected rows: {audit.affected_rows}")
    print(f"Affected paths: {len(audit.affected_paths)}")
    print(_format_totals("Before", audit.totals_before))
    print(_format_totals("After", audit.totals_after))
    if audit.affected_paths:
        print("Sample affected paths:")
        for path in audit.affected_paths[:20]:
            print(f"  - {path} -> {normalize_auth_usage_path_for_migration(path)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        default=USER_DATABASE_PATH,
        help="Path to auth.db (default: project auth.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration after printing the audit report",
    )
    args = parser.parse_args()

    audit = audit_api_usage_summary(args.db_path)
    print_audit_report(audit)

    if not args.apply:
        return 0

    result = migrate_api_usage_summary(args.db_path)
    if result["changed"]:
        print(f"Migration completed. Backup: {result['backup_path']}")
        print(f"Normalized rows affected: {result['affected_rows']}")
        print(f"Final summary rows: {result['final_rows']}")
    else:
        print("No migration needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
