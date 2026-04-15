import asyncio
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from app.routes.geo.get_locs import get_all_locs
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations
from app.sql.db_pool import close_all_pools


def create_query_db(rows):
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "query.db")

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE dialects (
            簡稱 TEXT,
            音典分區 TEXT,
            地圖集二分區 TEXT,
            存儲標記 TEXT
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO dialects (簡稱, 音典分區, 地圖集二分區, 存儲標記)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()

    return temp_dir, db_path


class QueryDialectAbbreviationsDedupTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(close_all_pools)

    def test_deduplicates_location_sequence_without_regions(self):
        temp_dir, db_path = create_query_db([])
        self.addCleanup(temp_dir.cleanup)

        result = query_dialect_abbreviations(
            region_input=None,
            location_sequence=["北京", "北京", "天津", "北京"],
            db_path=db_path,
        )

        self.assertEqual(result, ["北京", "天津"])

    def test_deduplicates_locations_overlapping_with_region_results(self):
        temp_dir, db_path = create_query_db([
            ("北京", "華北-河北", "官話", "1"),
        ])
        self.addCleanup(temp_dir.cleanup)

        result = query_dialect_abbreviations(
            region_input=["華北-河北"],
            location_sequence=["北京", "北京", "保定", "北京"],
            db_path=db_path,
        )

        self.assertEqual(result, ["北京", "保定"])


class GetAllLocsRouteDedupTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(close_all_pools)

    def test_route_returns_deduplicated_locations(self):
        temp_dir, db_path = create_query_db([])
        self.addCleanup(temp_dir.cleanup)

        duplicated_matches = [
            (["北京"], 1, [], [], [], [], [], []),
            (["北京"], 1, [], [], [], [], [], []),
        ]

        with patch(
            "app.routes.geo.get_locs.match_locations_batch_exact",
            return_value=duplicated_matches,
        ):
            result = asyncio.run(
                get_all_locs(
                    locations=["北京 北京"],
                    regions=None,
                    region_mode="yindian",
                    query_db=db_path,
                )
            )

        self.assertEqual(result, {"locations_result": ["北京"]})


if __name__ == "__main__":
    unittest.main()
