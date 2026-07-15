from __future__ import annotations

import argparse
import sqlite3

from app.common.path import TOPONYMS_DB_PATH


INDEX_STATEMENTS = (
    """
    CREATE INDEX IF NOT EXISTS idx_single_type_id
    ON single(place_type_code, id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_single_type_name_id
    ON single(place_type_code, standard_name, id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_single_type_name_area
    ON single(place_type_code, standard_name, area_code)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_single_type_lng_lat_id
    ON single(place_type_code, longitude, latitude, id)
    """,
)


def ensure_toponyms_indexes(db_path: str = TOPONYMS_DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        for statement in INDEX_STATEMENTS:
            conn.execute(statement)
        conn.execute("ANALYZE")
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create required indexes for data/toponyms.db")
    parser.add_argument("--db", default=TOPONYMS_DB_PATH, help="Path to toponyms.db")
    args = parser.parse_args()
    ensure_toponyms_indexes(args.db)


if __name__ == "__main__":
    main()
