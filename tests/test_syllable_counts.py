import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.schemas.core.phonology import SyllableCountsRequest
from app.service.core.feature_stats import (
    calculate_aggregated_feature_counts,
    get_feature_counts,
    get_feature_counts_for_request,
    get_syllable_counts,
    resolve_feature_locations,
)


def _create_query_db(path: Path, location_count: int = 0) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE dialects (
                簡稱 TEXT,
                音典分區 TEXT,
                地圖集二分區 TEXT,
                存儲標記 INTEGER,
                經緯度 TEXT
            )
            """
        )
        rows = [
            ("廣州", "珠三角-廣府", "廣東-珠三角", 1, "23.1291,113.2644"),
            ("香港", "珠三角-廣府", "廣東-珠三角", 1, "22.3193,114.1694"),
            ("無座標", "珠三角-廣府", "廣東-珠三角", 1, ""),
            ("潮州", "潮汕", "廣東-潮汕", 1, "23.6567,116.6226"),
        ]
        rows.extend(
            (f"批量{i}", "批量區", "批量區", 1, f"20.{i % 1000},110.{i % 1000}")
            for i in range(location_count)
        )
        conn.executemany("INSERT INTO dialects VALUES (?, ?, ?, ?, ?)", rows)


def _create_dialects_db(path: Path, location_count: int = 0) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE dialects (
                簡稱 TEXT,
                漢字 TEXT,
                聲母 TEXT,
                韻母 TEXT,
                聲調 TEXT,
                音節 TEXT
            )
            """
        )
        rows = [
            ("廣州", "詩", "s", "i", "55", "si55"),
            ("廣州", "詩", "s", "i", "55", "si55"),
            ("廣州", "時", "s", "i", "21", "si21"),
            ("廣州", "安", "", "on", "33", "on33"),
            ("廣州", "空音節", "k", "ong", "55", ""),
            ("廣州", "", "k", "ong", "55", "kong55"),
            ("香港", "詩", "s", "i", "55", "si55"),
            ("香港", "心", "s", "am", "55", "sam55"),
            ("香港", "安", None, "on", "33", "on33"),
            ("香港", "唔", "m", "", "21", "m21"),
            ("潮州", "詩", "s", "i", "1", "si1"),
            ("無座標", "詩", "s", "i", "55", "si55"),
        ]
        rows.extend(
            (f"批量{i}", "一", "", "a", "1", "a1")
            for i in range(location_count)
        )
        conn.executemany("INSERT INTO dialects VALUES (?, ?, ?, ?, ?, ?)", rows)


class SyllableCountsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dialects_db = str(Path(self.tmp.name) / "dialects.db")
        self.query_db = str(Path(self.tmp.name) / "query.db")
        _create_dialects_db(Path(self.dialects_db), location_count=1100)
        _create_query_db(Path(self.query_db), location_count=1100)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_syllable_counts_locations_only_returns_toned_and_toneless_aggregation(self) -> None:
        result = get_syllable_counts(["廣州", "香港"], self.dialects_db, self.query_db)

        self.assertEqual(result["toneless"]["locations"]["廣州"]["total_tokens"], 3)
        self.assertEqual(result["toneless"]["locations"]["廣州"]["unique_syllables"], 2)
        self.assertEqual(result["toneless"]["locations"]["廣州"]["syllables"], {"si": 2, "on": 1})
        self.assertEqual(result["toned"]["locations"]["廣州"]["syllables"], {"si55": 1, "si21": 1, "on33": 1})
        self.assertEqual(result["toneless"]["locations"]["香港"]["syllables"]["m"], 1)
        self.assertEqual(result["toned"]["locations"]["香港"]["syllables"]["m21"], 1)
        self.assertEqual(
            result["toneless"]["aggregated"]["syllables"]["si"],
            {"totalCount": 3, "locationCount": 2, "locations": ["廣州", "香港"]},
        )
        self.assertEqual(result["toneless"]["aggregated"]["total_tokens"], 7)
        self.assertEqual(result["toned"]["aggregated"]["unique_syllables"], 5)

    async def test_syllable_counts_regions_only_resolves_locations_and_counts(self) -> None:
        payload = SyllableCountsRequest(locations=[], regions=["潮汕"], region_mode="yindian")
        locations = resolve_feature_locations(payload.locations, payload.regions, self.query_db, payload.region_mode)

        result = get_syllable_counts(locations, self.dialects_db, self.query_db)

        self.assertEqual(result["meta"]["locations_count"], 1)
        self.assertEqual(result["toneless"]["locations"]["潮州"]["syllables"], {"si": 1})

    async def test_syllable_counts_locations_and_regions_merge_dedupes_stably(self) -> None:
        payload = SyllableCountsRequest(locations=["香港", "廣州"], regions=["珠三角"], region_mode="yindian")
        locations = resolve_feature_locations(payload.locations, payload.regions, self.query_db, payload.region_mode)

        result = get_syllable_counts(locations, self.dialects_db, self.query_db)

        self.assertEqual(list(result["toneless"]["locations"].keys()), ["廣州", "香港", "無座標"])
        self.assertEqual(result["meta"]["requested_locations_count"], 3)

    def test_syllable_counts_coordinates_points_and_missing_coordinate_meta(self) -> None:
        result = get_syllable_counts(["廣州", "無座標"], self.dialects_db, self.query_db)

        self.assertEqual(result["points"][0]["location"], "廣州")
        self.assertEqual(result["points"][0]["coordinate"], [113.2644, 23.1291])
        self.assertEqual(result["points"][0]["toneless"], {"si": 2, "on": 1})
        self.assertEqual(result["meta"]["locations_without_coordinates"], ["無座標"])

    async def test_feature_counts_locations_only_old_format_remains_unchanged(self) -> None:
        direct = get_feature_counts(["廣州", "香港"], self.dialects_db)
        routed = get_feature_counts_for_request(
            locations=["廣州", "香港"],
            regions=[],
            new_format=False,
            region_mode="yindian",
            dialects_db=self.dialects_db,
            query_db=self.query_db,
        )

        self.assertEqual(routed, direct)
        self.assertNotIn("locations", routed)
        self.assertEqual(calculate_aggregated_feature_counts(routed)["聲母"]["s"]["totalCount"], 4)

    async def test_feature_counts_regions_only_and_mixed_regions(self) -> None:
        regions_only = get_feature_counts_for_request(
            locations=[],
            regions=["潮汕"],
            new_format=True,
            region_mode="yindian",
            dialects_db=self.dialects_db,
            query_db=self.query_db,
        )
        mixed = get_feature_counts_for_request(
            locations=["廣州"],
            regions=["潮汕"],
            new_format=True,
            region_mode="yindian",
            dialects_db=self.dialects_db,
            query_db=self.query_db,
        )

        self.assertEqual(list(regions_only["locations"].keys()), ["潮州"])
        self.assertEqual(list(mixed["locations"].keys()), ["潮州", "廣州"])
        self.assertEqual(mixed["aggregated"]["聲母"]["s"]["locations"], ["潮州", "廣州"])

    def test_syllable_counts_handles_more_than_sqlite_single_statement_parameter_limit(self) -> None:
        locations = [f"批量{i}" for i in range(1100)]

        result = get_syllable_counts(locations, self.dialects_db, self.query_db, chunk_size=400)

        self.assertEqual(result["meta"]["requested_locations_count"], 1100)
        self.assertEqual(result["meta"]["locations_count"], 1100)
        self.assertEqual(result["toned"]["aggregated"]["syllables"]["a1"]["totalCount"], 1100)
        self.assertEqual(len(result["points"]), 1100)

    def test_feature_counts_chunks_under_sqlite_parameter_limit(self) -> None:
        locations = [f"批量{i}" for i in range(400)]

        result = get_feature_counts(locations, self.dialects_db)

        self.assertEqual(len(result), 400)
        self.assertEqual(result["批量0"]["聲母"][""], 1)
        self.assertEqual(result["批量399"]["韻母"]["a"], 1)
        self.assertEqual(result["批量399"]["聲調"]["1"], 1)

    async def test_syllable_counts_rejects_empty_locations_and_regions(self) -> None:
        with self.assertRaises(ValueError):
            SyllableCountsRequest(locations=[], regions=[])

        with self.assertRaises(ValueError):
            get_feature_counts_for_request(
                locations=["  "],
                regions=[],
                new_format=False,
                region_mode="yindian",
                dialects_db=self.dialects_db,
                query_db=self.query_db,
            )


if __name__ == "__main__":
    unittest.main()
