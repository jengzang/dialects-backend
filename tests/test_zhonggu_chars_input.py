import unittest
from unittest.mock import patch

from app.routes.core import new_pho


class TestZhongGuCharsMerge(unittest.IsolatedAsyncioTestCase):
    async def test_only_chars_bypass_charlist_and_split(self):
        payload = type(
            "Payload",
            (),
            {
                "path_strings": None,
                "chars": ["笨蛋", "笨"],
                "column": None,
                "combine_query": False,
                "exclude_columns": None,
                "table_name": "characters",
                "locations": ["廣州石牌"],
                "regions": [],
                "features": ["韻母"],
                "region_mode": "yindian",
                "include_custom": False,
            },
        )()

        with patch("app.routes.core.new_pho.generate_combinations_and_query") as gen_mock, patch(
            "app.routes.core.new_pho.run_in_threadpool"
        ) as thread_mock:
            thread_mock.return_value = [{"ok": True}]

            result = await new_pho.analyze_zhonggu(
                payload=payload,
                dialects_db="dialects.db",
                query_db="query.db",
                user=None,
                custom_db=None,
            )

        gen_mock.assert_not_called()
        args, kwargs = thread_mock.call_args
        self.assertIs(args[0], new_pho._run_dialect_analysis_sync)
        self.assertEqual(
            kwargs["char_data_list"],
            [
                {
                    "query": "字集",
                    "char_count": 2,
                    "chars": ["笨", "蛋"],
                    "字数": 2,
                    "汉字": ["笨", "蛋"],
                    "漢字": ["笨", "蛋"],
                }
            ],
        )
        self.assertEqual(result["status"], "success")

    async def test_only_path_strings_keep_existing_logic(self):
        payload = type(
            "Payload",
            (),
            {
                "path_strings": ["[知]{組}"],
                "chars": None,
                "column": None,
                "combine_query": False,
                "exclude_columns": None,
                "table_name": "characters",
                "locations": ["廣州石牌"],
                "regions": [],
                "features": ["韻母"],
                "region_mode": "yindian",
                "include_custom": False,
            },
        )()

        cached_result = [
            {
                "query": "知組",
                "char_count": 2,
                "chars": ["知", "脂"],
                "字数": 2,
                "汉字": ["知", "脂"],
                "漢字": ["知", "脂"],
            }
        ]

        with patch("app.routes.core.new_pho.generate_combinations_and_query", return_value=cached_result) as gen_mock, patch(
            "app.routes.core.new_pho.run_in_threadpool"
        ) as thread_mock:
            thread_mock.return_value = [{"ok": True}]

            await new_pho.analyze_zhonggu(
                payload=payload,
                dialects_db="dialects.db",
                query_db="query.db",
                user=None,
                custom_db=None,
            )

        gen_mock.assert_called_once()
        args, kwargs = thread_mock.call_args
        self.assertEqual(kwargs["char_data_list"], cached_result)

    async def test_chars_and_path_strings_merge_with_path_priority(self):
        payload = type(
            "Payload",
            (),
            {
                "path_strings": ["[知]{組}"],
                "chars": ["知笨"],
                "column": None,
                "combine_query": False,
                "exclude_columns": None,
                "table_name": "characters",
                "locations": ["廣州石牌"],
                "regions": [],
                "features": ["韻母"],
                "region_mode": "yindian",
                "include_custom": False,
            },
        )()

        cached_result = [
            {
                "query": "知組",
                "char_count": 2,
                "chars": ["知", "脂"],
                "字数": 2,
                "汉字": ["知", "脂"],
                "漢字": ["知", "脂"],
            }
        ]

        with patch("app.routes.core.new_pho.generate_combinations_and_query", return_value=cached_result), patch(
            "app.routes.core.new_pho.run_in_threadpool"
        ) as thread_mock:
            thread_mock.return_value = [{"ok": True}]

            await new_pho.analyze_zhonggu(
                payload=payload,
                dialects_db="dialects.db",
                query_db="query.db",
                user=None,
                custom_db=None,
            )

        args, kwargs = thread_mock.call_args
        self.assertEqual(
            kwargs["char_data_list"],
            [
                {
                    "query": "知組",
                    "char_count": 3,
                    "chars": ["知", "脂", "笨"],
                    "字数": 3,
                    "汉字": ["知", "脂", "笨"],
                    "漢字": ["知", "脂", "笨"],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
