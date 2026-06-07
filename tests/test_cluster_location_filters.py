import unittest
from unittest.mock import patch

from app.tools.cluster.service.resolver_service import resolve_locations


class ClusterLocationFilterTests(unittest.TestCase):
    def test_resolve_locations_filters_year_prefixed_locations_by_default(self) -> None:
        with patch(
            "app.tools.cluster.service.resolver_service.query_dialect_abbreviations",
            return_value=["1935新長沙", "長沙", "域外測試點"],
        ), patch(
            "app.tools.cluster.service.resolver_service.match_locations_batch_exact",
            return_value=[
                (["1935新長沙"], 1, None, None),
                (["長沙"], 1, None, None),
                (["域外測試點"], 1, None, None),
            ],
        ), patch(
            "app.tools.cluster.service.resolver_service.load_location_filter_details",
            return_value={
                "1935新長沙": {
                    "location": "1935新長沙",
                    "yindian_region": "湘贛-北湘-星城",
                    "map_region": "湘語-長益片-長株潭小片",
                },
                "長沙": {
                    "location": "長沙",
                    "yindian_region": "湘贛-北湘-星城",
                    "map_region": "湘語-長益片-長株潭小片",
                },
                "域外測試點": {
                    "location": "域外測試點",
                    "yindian_region": "域外方音",
                    "map_region": None,
                },
            },
        ):
            result = resolve_locations(
                locations=["1935新長沙", "長沙", "域外測試點"],
                regions=[],
                region_mode="yindian",
                query_db="fake.db",
            )

        self.assertEqual(result["matched_locations"], ["長沙"])
        self.assertEqual(result["filtered_year_locations"], ["1935新長沙"])
        self.assertEqual(result["filtered_year_location_count"], 1)
        self.assertEqual(result["filtered_special_locations"], ["域外測試點"])
        self.assertEqual(result["filtered_special_location_count"], 1)


if __name__ == "__main__":
    unittest.main()
