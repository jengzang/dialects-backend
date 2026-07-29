#!/usr/bin/env python3
"""Delete duplicate vocabulary_entries, keeping the row with the smallest id per group.

Groups are defined by (user_id, location_name, standard_word, local_expression).

Usage:
    python scripts/vocabulary/dedup_entries.py [--dry-run] [--yes]

Options:
    --dry-run   Report duplicates without deleting
    --yes       Skip confirmation prompt
"""

import sys
from app.service.vocabulary.database import SessionLocal

DRY_RUN_SQL = """
SELECT
    user_id,
    location_name,
    standard_word,
    local_expression,
    COUNT(*) AS total_rows,
    COUNT(*) - 1 AS excess_count
FROM vocabulary_entries
GROUP BY user_id, location_name, standard_word, local_expression
HAVING COUNT(*) > 1
ORDER BY excess_count DESC
"""

DELETE_SQL = """
DELETE FROM vocabulary_entries
WHERE id NOT IN (
    SELECT keep_id FROM (
        SELECT MIN(id) AS keep_id
        FROM vocabulary_entries
        GROUP BY user_id, location_name, standard_word, local_expression
    )
)
"""


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    skip_confirm = "--yes" in sys.argv

    session = SessionLocal()
    try:
        conn = session.connection().connection
        cursor = conn.cursor()

        cursor.execute(DRY_RUN_SQL)
        dup_groups = cursor.fetchall()

        if not dup_groups:
            print("No duplicate entries found.")
            return

        total_excess = sum(row[4] for row in dup_groups)
        print(f"Found {len(dup_groups)} duplicate groups ({total_excess} excess rows)")
        print()
        print("Top 20 duplicate groups:")
        print(f"{'user_id':<10} {'location':<16} {'standard_word':<16} {'local_expr':<16} {'total':>6} {'excess':>6}")
        print("-" * 76)
        for row in dup_groups[:20]:
            print(
                f"{row[0]:<10} {row[1]:<16} {row[2]:<16} {row[3]:<16} {row[4]:>6} {row[5]:>6}"
            )

        if dry_run:
            print()
            print("Dry run — no changes made. Remove --dry-run to execute.")
            return

        print()
        if not skip_confirm:
            response = input(f"Delete {total_excess} duplicate rows? [y/N] ")
            if response.lower() not in ("y", "yes"):
                print("Aborted.")
                return

        cursor.execute("BEGIN")
        cursor.execute(DELETE_SQL)
        deleted = cursor.rowcount
        cursor.execute("COMMIT")

        print(f"Deleted {deleted} rows. {len(dup_groups)} groups now have a single row each.")

    finally:
        session.close()


if __name__ == "__main__":
    main()
