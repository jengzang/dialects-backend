import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from app.routes.core.phonology import run_phonology_analysis
from app.schemas.core.phonology import AnalysisPayload
from app.service.core.feature_stats import get_feature_statistics
from app.service.core.status_arrange_pho import sta2pho, run_status


class PhonologyMultiTableSupportTests(unittest.TestCase):
    def test_analysis_payload_preserves_table_name(self) -> None:
        payload = AnalysisPayload(
            mode="s2p",
            locations=["廣州"],
            regions=[],
            features=["聲母"],
            status_inputs=["[云]{聲母}"],
            table_name="fenyun",
        )

        self.assertEqual(payload.model_dump()["table_name"], "fenyun")

    def test_run_phonology_analysis_passes_table_to_sta2pho(self) -> None:
        with patch("app.routes.core.phonology.sta2pho", return_value=[]) as mock_sta2pho:
            run_phonology_analysis(
                mode="s2p",
                locations=["廣州"],
                regions=[],
                features=["聲母"],
                status_inputs=["[云]{聲母}"],
                table_name="fenyun",
            )

        self.assertEqual(mock_sta2pho.call_args.kwargs["table"], "fenyun")

    def test_run_phonology_analysis_passes_table_to_pho2sta(self) -> None:
        with patch("app.routes.core.phonology.pho2sta", return_value=[]) as mock_pho2sta:
            run_phonology_analysis(
                mode="p2s",
                locations=["廣州"],
                regions=[],
                features=["聲母"],
                group_inputs=["聲母"],
                pho_values=["w"],
                table_name="fenyun",
            )

        self.assertEqual(mock_pho2sta.call_args.kwargs["table"], "fenyun")

    def test_run_status_accepts_explicit_path_query_for_non_character_table(self) -> None:
        with patch(
            "app.service.core.status_arrange_pho.query_characters_by_path",
            return_value=(["云"], []),
        ) as mock_query:
            result = run_status(["[云]{聲母}"], table="fenyun")

        self.assertEqual(mock_query.call_args.kwargs["table"], "fenyun")
        self.assertEqual(result[0][1], ["云"])

    def test_sta2pho_auto_generates_path_queries_for_non_character_tables(self) -> None:
        fake_pool = MagicMock()
        fake_pool.get_connection.return_value.__enter__.return_value = object()

        with (
            patch(
                "app.service.core.status_arrange_pho.query_dialect_abbreviations",
                return_value=["廣州"],
            ),
            patch(
                "app.service.core.status_arrange_pho.match_locations_batch_exact",
                return_value=[(["廣州"], 1)],
            ),
            patch("app.service.core.status_arrange_pho.get_db_pool", return_value=fake_pool),
            patch(
                "app.service.core.status_arrange_pho.pd.read_sql_query",
                return_value=pd.DataFrame({"聲母": ["云", "以"]}),
            ) as mock_read_sql,
            patch(
                "app.service.core.status_arrange_pho.run_status",
                return_value=[("[云]{聲母}", False, False, [])],
            ) as mock_run_status,
        ):
            sta2pho(
                locations=["廣州"],
                regions=[],
                features=["聲母"],
                test_inputs=None,
                table="fenyun",
            )

        self.assertIn('FROM "fenyun"', mock_read_sql.call_args.args[0])
        self.assertTrue(all(call.kwargs["table"] == "fenyun" for call in mock_run_status.call_args_list))
        generated_inputs = [call.args[0][0] for call in mock_run_status.call_args_list]
        self.assertEqual(generated_inputs, ["[云]{聲母}", "[以]{聲母}"])

    def test_feature_stats_returns_wenbai_read_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "dialects.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE dialects (
                        簡稱 TEXT,
                        漢字 TEXT,
                        聲母 TEXT,
                        韻母 TEXT,
                        聲調 TEXT,
                        多音字 TEXT
                    )
                    """
                )
                conn.executemany(
                    "INSERT INTO dialects VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        ("測試點", "A", "k", "a", "陰平", "1"),
                        ("測試點", "B", "k", "a", "陰平", "2"),
                        ("測試點", "B", "k", "a", "陰平", "3"),
                        ("測試點", "C", "k", "a", "陰平", "2"),
                        ("測試點", "D", "k", "a", "陰平", "3"),
                        ("測試點", "E", "k", "a", "陰平", None),
                    ],
                )

            result = get_feature_statistics(
                locations=["測試點"],
                features=["聲母"],
                db_path=str(db_path),
            )

        self.assertEqual(result["chars_map"], ["A", "B", "C", "D", "E"])
        self.assertEqual(
            result["data"]["測試點"]["聲母"]["k"]["read_stats"],
            {
                "polyphonic": {"count": 4, "char_indices": [0, 1, 2, 3]},
                "wendu": {"count": 2, "char_indices": [1, 2]},
                "baidu": {"count": 2, "char_indices": [1, 3]},
                "wenbai": {"count": 1, "char_indices": [1]},
            },
        )


if __name__ == "__main__":
    unittest.main()
