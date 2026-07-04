import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routes.user.custom_data import (
    get_custom_data_by_feature,
    get_custom_data_by_point,
    get_user_custom_counts,
    get_user_custom_feature_groups,
    get_user_custom_points,
    list_grouped_features_for_user,
    list_grouped_points_for_user,
    list_records_by_feature_for_user,
    list_records_by_point_for_user,
    list_user_custom_counts,
)
from app.service.user.submission.get_custom import get_from_submission
from app.service.user.core.models import Information


class _FakeOrderField:
    def desc(self):
        return self

    def asc(self):
        return self


class _FakeInformation:
    created_at = _FakeOrderField()


class _FakeAggregateQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeRecordQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, query_obj):
        self._query_obj = query_obj
        self.closed = False

    def query(self, *args, **kwargs):
        return self._query_obj

    def close(self):
        self.closed = True


class _FakeDistinctQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def all(self):
        return self._rows


class _FakeRecordFilterQuery:
    def __init__(self, record_map):
        self._record_map = record_map
        self._current_location = None
        self._effective_filters = {}

    def filter(self, *args, **kwargs):
        for clause in args:
            right = getattr(clause, "right", None)
            value = getattr(right, "value", None)
            left = getattr(clause, "left", None)
            column_name = getattr(left, "name", None)
            if column_name == "簡稱":
                self._current_location = value
            elif column_name in {"特徵", "聲韻調"} and hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
                self._effective_filters[column_name] = set(value)
            elif column_name in {"特徵", "聲韻調"}:
                self._effective_filters[column_name] = {value}
        return self

    def all(self):
        rows = list(self._record_map.get(self._current_location, []))
        feature_values = self._effective_filters.get("特徵")
        phonology_values = self._effective_filters.get("聲韻調")
        if feature_values is not None:
            rows = [row for row in rows if getattr(row, "特徵", None) in feature_values]
        if phonology_values is not None:
            rows = [row for row in rows if getattr(row, "聲韻調", None) in phonology_values]
        return rows


class _FakeSubmissionSession:
    def __init__(self, custom_locations, record_map):
        self._custom_locations = [(loc,) for loc in custom_locations]
        self._record_map = record_map

    def query(self, entity, *args, **kwargs):
        if entity is Information.簡稱:
            return _FakeDistinctQuery(self._custom_locations)
        if entity is Information:
            return _FakeRecordFilterQuery(self._record_map)
        raise AssertionError(f"unexpected query target: {entity}")


class CustomDataReadApisTests(unittest.IsolatedAsyncioTestCase):
    async def test_counts_endpoint_exposes_user_custom_totals(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        expected = {
            "success": True,
            "custom_region_total": 3,
            "custom_data_total": 28,
        }

        with patch(
            "app.routes.user.custom_data.list_user_custom_counts",
            return_value=expected,
        ) as mock_service:
            result = await get_user_custom_counts(current_user=user)

        self.assertEqual(result, expected)
        self.assertEqual(mock_service.call_args.args, (user,))

    async def test_points_endpoint_exposes_grouped_cards(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        expected = {
            "success": True,
            "data": [
                {
                    "point_key": "陽春圭崗||嶺南",
                    "簡稱": "陽春圭崗",
                    "音典分區": "嶺南",
                    "經緯度": "111.742615,22.356760",
                    "feature_count": 2,
                    "updated_at": datetime(2026, 6, 5, 10, 0, 0),
                }
            ],
            "total": 1,
        }

        with patch(
            "app.routes.user.custom_data.list_grouped_points_for_user",
            return_value=expected,
        ) as mock_service:
            result = await get_user_custom_points(keyword="陽春", current_user=user)

        self.assertEqual(result, expected)
        self.assertEqual(mock_service.call_args.args, (user, "陽春"))

    async def test_features_endpoint_exposes_grouped_cards(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        expected = {
            "success": True,
            "data": [
                {
                    "feature_key": "流攝||韻母",
                    "特徵": "流攝",
                    "聲韻調": "韻母",
                    "location_count": 2,
                    "updated_at": datetime(2026, 6, 5, 10, 0, 0),
                }
            ],
            "total": 1,
        }

        with patch(
            "app.routes.user.custom_data.list_grouped_features_for_user",
            return_value=expected,
        ) as mock_service:
            result = await get_user_custom_feature_groups(keyword="流", current_user=user)

        self.assertEqual(result, expected)
        self.assertEqual(mock_service.call_args.args, (user, "流"))

    async def test_data_by_point_requires_login(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await get_custom_data_by_point(location="陽春圭崗", region="嶺南", current_user=None)
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_data_by_point_returns_stable_records(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        expected_records = [
            {
                "簡稱": "陽春圭崗",
                "音典分區": "嶺南",
                "經緯度": "111.742615,22.356760",
                "聲韻調": "韻母",
                "特徵": "流攝",
                "值": "eu",
                "說明": "老派讀音",
                "created_at": datetime(2026, 6, 1, 10, 0, 0),
            }
        ]

        with patch(
            "app.routes.user.custom_data.list_records_by_point_for_user",
            return_value=expected_records,
        ) as mock_service, patch(
            "app.routes.user.custom_data.Information",
            _FakeInformation,
        ):
            result = await get_custom_data_by_point(location="陽春圭崗", region="嶺南", current_user=user)

        self.assertEqual(result, {"success": True, "data": expected_records})
        self.assertEqual(mock_service.call_args.args, (user, "陽春圭崗", "嶺南"))

    async def test_data_by_feature_returns_stable_records(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        expected_records = [
            {
                "簡稱": "陽春圭崗",
                "音典分區": "嶺南",
                "經緯度": "111.742615,22.356760",
                "聲韻調": "韻母",
                "特徵": "流攝",
                "值": "eu",
                "說明": "",
                "created_at": datetime(2026, 6, 1, 10, 0, 0),
            }
        ]

        with patch(
            "app.routes.user.custom_data.list_records_by_feature_for_user",
            return_value=expected_records,
        ) as mock_service, patch(
            "app.routes.user.custom_data.Information",
            _FakeInformation,
        ):
            result = await get_custom_data_by_feature(feature="流攝", phonology="韻母", current_user=user)

        self.assertEqual(result, {"success": True, "data": expected_records})
        self.assertEqual(mock_service.call_args.args, (user, "流攝", "韻母"))


class CustomDataReadServiceTests(unittest.TestCase):
    def test_get_from_submission_keeps_direct_custom_locations_when_mixed_with_standard_locations(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        record = SimpleNamespace(
            簡稱="test1",
            聲韻調="韻母",
            特徵="流攝",
            值="eu",
            maxValue="9",
            經緯度="111.1,22.2",
            說明="自定義",
            created_at=datetime(2026, 6, 1, 10, 0, 0),
        )
        db = _FakeSubmissionSession(custom_locations=["test1"], record_map={"test1": [record]})

        with patch(
            "app.service.user.submission.get_custom.query_dialect_abbreviations_orm",
            return_value=[],
        ) as mock_abbr:
            result = get_from_submission(
                locations=["test1", "北京"],
                regions=[],
                need_features=["流攝"],
                user=user,
                db=db,
                phonology_list=["韻母"],
            )

        self.assertEqual(mock_abbr.call_args.args[3], [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["簡稱"], "test1")
        self.assertEqual(result[0]["特徵"], "流攝")
        self.assertEqual(result[0]["經緯度"], [111.1, 22.2])

    def test_get_from_submission_splits_space_joined_locations_and_keeps_custom_hits(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        record = SimpleNamespace(
            簡稱="茶山增埗",
            聲韻調="韻母",
            特徵="流",
            值="iu",
            maxValue="9",
            經緯度="113.0,23.0",
            說明="空格混合輸入",
            created_at=datetime(2026, 6, 1, 10, 0, 0),
        )
        db = _FakeSubmissionSession(custom_locations=["茶山增埗"], record_map={"茶山增埗": [record]})

        with patch(
            "app.service.user.submission.get_custom.query_dialect_abbreviations_orm",
            return_value=[],
        ):
            result = get_from_submission(
                locations=["廣州 茶山增埗"],
                regions=[],
                need_features=["流"],
                user=user,
                db=db,
                phonology_list=["韻母"],
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["簡稱"], "茶山增埗")
        self.assertEqual(result[0]["特徵"], "流")
        self.assertEqual(result[0]["經緯度"], [113.0, 23.0])

    def test_get_from_submission_allows_featureless_phonology_filter_for_tone_payloads(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        tone_record = SimpleNamespace(
            簡稱="茶山增埗",
            聲韻調="調值",
            特徵="陰平",
            值="55",
            maxValue="55",
            經緯度="113.0,23.0",
            說明="調值記錄",
            created_at=datetime(2026, 6, 1, 10, 0, 0),
        )
        non_tone_record = SimpleNamespace(
            簡稱="茶山增埗",
            聲韻調="韻母",
            特徵="流",
            值="iu",
            maxValue="iu",
            經緯度="113.0,23.0",
            說明="非調值",
            created_at=datetime(2026, 6, 1, 10, 5, 0),
        )
        db = _FakeSubmissionSession(
            custom_locations=["茶山增埗"],
            record_map={"茶山增埗": [tone_record, non_tone_record]},
        )

        with patch(
            "app.service.user.submission.get_custom.query_dialect_abbreviations_orm",
            return_value=[],
        ):
            result = get_from_submission(
                locations=["茶山增埗"],
                regions=[],
                need_features=[],
                user=user,
                db=db,
                phonology_list=["調值"],
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["聲韻調"], "調值")
        self.assertEqual(result[0]["特徵"], "陰平")

    def test_get_from_submission_filters_feature_and_phonology_together(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        char_record = SimpleNamespace(
            簡稱="茶山增埗",
            聲韻調="漢字",
            特徵="笨",
            值="pən",
            maxValue="pən",
            經緯度="113.0,23.0",
            說明="漢字記錄",
            created_at=datetime(2026, 6, 1, 10, 0, 0),
        )
        other_char_record = SimpleNamespace(
            簡稱="茶山增埗",
            聲韻調="漢字",
            特徵="蛋",
            值="tan",
            maxValue="tan",
            經緯度="113.0,23.0",
            說明="另一字",
            created_at=datetime(2026, 6, 1, 10, 5, 0),
        )
        db = _FakeSubmissionSession(
            custom_locations=["茶山增埗"],
            record_map={"茶山增埗": [char_record, other_char_record]},
        )

        with patch(
            "app.service.user.submission.get_custom.query_dialect_abbreviations_orm",
            return_value=[],
        ):
            result = get_from_submission(
                locations=["茶山增埗"],
                regions=[],
                need_features=["笨"],
                user=user,
                db=db,
                phonology_list=["漢字"],
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["特徵"], "笨")
        self.assertEqual(result[0]["聲韻調"], "漢字")

    def test_counts_service_returns_region_and_data_totals(self) -> None:
        user = SimpleNamespace(id=7, username="tester")

        class _FakeCountQuery:
            def __init__(self, value):
                self.value = value

            def filter(self, *args, **kwargs):
                return self

            def count(self):
                return self.value

        class _FakeCountSession:
            def __init__(self):
                self.closed = False
                self.calls = 0

            def query(self, *args, **kwargs):
                self.calls += 1
                return _FakeCountQuery(3 if self.calls == 1 else 28)

            def close(self):
                self.closed = True

        fake_session = _FakeCountSession()

        with patch("app.routes.user.custom_data.SessionLocal_info", return_value=fake_session):
            result = list_user_custom_counts(user)

        self.assertTrue(fake_session.closed)
        self.assertEqual(result, {
            "success": True,
            "custom_region_total": 3,
            "custom_data_total": 28,
        })

    def test_grouped_points_service_shapes_rows(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        rows = [
            SimpleNamespace(
                簡稱="陽春圭崗",
                音典分區="嶺南",
                經緯度="111.742615,22.356760",
                feature_count=12,
                updated_at=datetime(2026, 6, 5, 10, 0, 0),
            )
        ]
        fake_session = _FakeSession(_FakeAggregateQuery(rows))

        with patch("app.routes.user.custom_data.SessionLocal_info", return_value=fake_session):
            result = list_grouped_points_for_user(user, keyword="陽春")

        self.assertTrue(fake_session.closed)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["data"][0]["point_key"], "陽春圭崗||嶺南")
        self.assertEqual(result["data"][0]["feature_count"], 12)

    def test_grouped_features_service_shapes_rows(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        rows = [
            SimpleNamespace(
                特徵="流攝",
                聲韻調="韻母",
                location_count=5,
                updated_at=datetime(2026, 6, 5, 10, 0, 0),
            )
        ]
        fake_session = _FakeSession(_FakeAggregateQuery(rows))

        with patch("app.routes.user.custom_data.SessionLocal_info", return_value=fake_session):
            result = list_grouped_features_for_user(user, keyword="流")

        self.assertTrue(fake_session.closed)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["data"][0]["feature_key"], "流攝||韻母")
        self.assertEqual(result["data"][0]["location_count"], 5)

    def test_records_by_point_service_serializes_rows(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        row = Information(
            簡稱="陽春圭崗",
            音典分區="嶺南",
            經緯度="111.742615,22.356760",
            聲韻調="韻母",
            特徵="流攝",
            值="eu",
            說明="老派讀音",
            maxValue="u",
            user_id=7,
            username="tester",
            created_at=datetime(2026, 6, 1, 10, 0, 0),
        )
        row.id = 1
        fake_session = _FakeSession(_FakeRecordQuery([row]))

        with patch("app.routes.user.custom_data.SessionLocal_info", return_value=fake_session):
            result = list_records_by_point_for_user(user, "陽春圭崗", "嶺南")

        self.assertTrue(fake_session.closed)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["簡稱"], "陽春圭崗")
        self.assertEqual(result[0]["值"], "eu")

    def test_records_by_feature_service_serializes_rows(self) -> None:
        user = SimpleNamespace(id=7, username="tester")
        row = Information(
            簡稱="陽春圭崗",
            音典分區="嶺南",
            經緯度="111.742615,22.356760",
            聲韻調="韻母",
            特徵="流攝",
            值="eu",
            說明="",
            maxValue="u",
            user_id=7,
            username="tester",
            created_at=datetime(2026, 6, 1, 10, 0, 0),
        )
        row.id = 2
        fake_session = _FakeSession(_FakeRecordQuery([row]))

        with patch("app.routes.user.custom_data.SessionLocal_info", return_value=fake_session):
            result = list_records_by_feature_for_user(user, "流攝", "韻母")

        self.assertTrue(fake_session.closed)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["特徵"], "流攝")
        self.assertEqual(result[0]["聲韻調"], "韻母")


if __name__ == "__main__":
    unittest.main()
