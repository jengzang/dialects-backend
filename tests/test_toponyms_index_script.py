import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from scripts.toponyms.ensure_indexes import ensure_toponyms_indexes


def create_minimal_toponyms_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE single (
            id TEXT PRIMARY KEY,
            standard_name TEXT,
            place_type TEXT,
            place_type_code TEXT,
            area_code TEXT,
            longitude REAL,
            latitude REAL
        );
        """
    )
    conn.commit()
    conn.close()


class ToponymsIndexScriptTest(unittest.TestCase):
    def test_ensure_toponyms_indexes_creates_required_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "toponyms.db")
            create_minimal_toponyms_db(db_path)

            ensure_toponyms_indexes(db_path)

            conn = sqlite3.connect(db_path)
            indexes = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                ).fetchall()
            }
            conn.close()

        self.assertIn("idx_single_type_id", indexes)
        self.assertIn("idx_single_type_name", indexes)


if __name__ == "__main__":
    unittest.main()
