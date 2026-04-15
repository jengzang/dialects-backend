import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from app.routes.core.phonology import run_phonology_analysis
from app.schemas.core.phonology import AnalysisPayload
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


if __name__ == "__main__":
    unittest.main()
