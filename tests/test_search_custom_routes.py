import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.routes.core import search as search_routes


class SearchRoutesCustomDataTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_tones_include_custom_queries_tone_payloads_only(self) -> None:
        user = SimpleNamespace(id=7, username="tester")

        with patch(
            "app.routes.core.search.run_in_threadpool"
        ) as thread_mock:
            def side_effect(func, *args, **kwargs):
                if func is search_routes.match_locations_batch_all:
                    return ["茶山增埗"]
                if func is search_routes.search_tones:
                    return [{"簡稱": "茶山增埗", "總數據": []}]
                if func is search_routes.get_from_submission:
                    self.assertEqual(args[0], ["茶山增埗"])
                    self.assertEqual(args[1], [])
                    self.assertEqual(args[2], [])
                    self.assertEqual(args[5], ["調值"])
                    return [{"簡稱": "茶山增埗", "聲韻調": "調值", "特徵": "陰平", "值": "55"}]
                raise AssertionError(f"unexpected func: {func}")

            thread_mock.side_effect = side_effect
            result = await search_routes.search_tones_o(
                locations=["茶山增埗"],
                regions=[],
                region_mode="yindian",
                include_custom=True,
                db=object(),
                custom_db=object(),
                query_db="query.db",
                user=user,
            )

        self.assertEqual(result["custom_data"], [{"簡稱": "茶山增埗", "聲韻調": "調值", "特徵": "陰平", "值": "55"}])
        self.assertEqual(result["tones_result"], [{"簡稱": "茶山增埗", "總數據": []}])

    async def test_search_chars_include_custom_queries_hanzi_payloads_only(self) -> None:
        user = SimpleNamespace(id=7, username="tester")

        with patch(
            "app.routes.core.search.run_in_threadpool"
        ) as thread_mock:
            def side_effect(func, *args, **kwargs):
                if func is search_routes.match_locations_batch_all:
                    return ["茶山增埗"]
                if func is search_routes.search_characters:
                    return {"result": [{"簡稱": "茶山增埗"}], "char_meta": {"笨": []}}
                if func is search_routes.search_tones:
                    return [{"簡稱": "茶山增埗", "總數據": []}]
                if func is search_routes.get_from_submission:
                    self.assertEqual(args[0], ["茶山增埗"])
                    self.assertEqual(args[1], [])
                    self.assertEqual(args[2], ["笨"])
                    self.assertEqual(args[5], ["漢字"])
                    return [{"簡稱": "茶山增埗", "聲韻調": "漢字", "特徵": "笨", "值": "pən"}]
                raise AssertionError(f"unexpected func: {func}")

            thread_mock.side_effect = side_effect
            result = await search_routes.search_chars(
                chars=["笨"],
                locations=["茶山增埗"],
                regions=[],
                region_mode="yindian",
                table_name="characters",
                response_mode="compact",
                include_custom=True,
                db=object(),
                custom_db=object(),
                dialects_db="dialects.db",
                query_db="query.db",
                user=user,
            )

        self.assertEqual(result["custom_data"], [{"簡稱": "茶山增埗", "聲韻調": "漢字", "特徵": "笨", "值": "pən"}])
        self.assertEqual(result["result"], [{"簡稱": "茶山增埗"}])
        self.assertEqual(result["char_meta"], {"笨": []})


if __name__ == "__main__":
    unittest.main()
