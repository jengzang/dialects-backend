import unittest
from unittest.mock import patch

import pandas as pd

from app.service.core import status_arrange_pho as sap


class _FakePool:
    def __init__(self, rows):
        self.rows = rows

    def get_connection(self):
        rows = self.rows

        class _Ctx:
            def __enter__(self_inner):
                class _Cursor:
                    def execute(self, query, params):
                        self.query = query
                        self.params = params

                    def fetchall(self):
                        return rows

                class _Conn:
                    def cursor(self):
                        return _Cursor()

                return _Conn()

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Ctx()


class QueryByStatusLogicTests(unittest.TestCase):
    def test_query_by_status_preserves_polyphonic_wendu_baidu_color_and_empty_location(self):
        rows = [
            ('甲地', '甲', 'a', '2', 'ka2'),
            ('甲地', '甲', 'a', '3', 'ka3'),
            ('甲地', '乙', 'a', '0', 'yi1'),
            ('甲地', '丙', 'b', '1', 'bing1'),
            ('甲地', '丙', 'b', '1', 'bing2'),
        ]

        with patch.object(sap, 'get_db_pool', return_value=_FakePool(rows)):
            df = sap.query_by_status(
                char_list=['甲', '乙', '丙'],
                locations=['甲地', '乙地'],
                features=['韻母'],
                user_input='測試輸入',
                db_path='ignored.db',
            )

        self.assertIsInstance(df, pd.DataFrame)
        records = df.to_dict(orient='records')
        self.assertEqual(len(records), 3)

        row_a = next(r for r in records if r['地點'] == '甲地' and r['分組值'] == {'測試輸入': 'a'})
        self.assertEqual(row_a['字數'], 2)
        self.assertEqual(row_a['佔比'], 0.6667)
        self.assertEqual(row_a['對應字'], ['乙', '甲'])
        self.assertEqual(row_a['多音字詳情'], '甲:文·ka2|白·ka3')
        self.assertEqual(row_a['文讀詳情'], '甲:ka2')
        self.assertEqual(row_a['白讀詳情'], '甲:ka3')
        self.assertEqual(row_a['color'], {'文白讀': ['甲']})

        row_b = next(r for r in records if r['地點'] == '甲地' and r['分組值'] == {'測試輸入': 'b'})
        self.assertEqual(row_b['字數'], 1)
        self.assertEqual(row_b['佔比'], 0.3333)
        self.assertEqual(row_b['對應字'], ['丙'])
        self.assertEqual(row_b['多音字詳情'], '丙:bing1|bing2')
        self.assertNotIn('文讀詳情', row_b)
        self.assertNotIn('白讀詳情', row_b)
        self.assertEqual(row_b['color'], {'多音字': ['丙']})

        empty_row = next(r for r in records if r['地點'] == '乙地')
        self.assertEqual(empty_row['特徵類別'], '無')
        self.assertEqual(empty_row['特徵值'], '無')
        self.assertEqual(empty_row['分組值'], {})
        self.assertEqual(empty_row['字數'], 0)
        self.assertEqual(empty_row['佔比'], 0.0)
        self.assertEqual(empty_row['對應字'], [])
        self.assertEqual(empty_row['多音字詳情'], '[X] 無符合漢字')
        self.assertEqual(empty_row['color'], {})


if __name__ == '__main__':
    unittest.main()
