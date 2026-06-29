import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.service.user.submission.delete import handle_form_deletion


class _FakeDeleteQuery:
    def __init__(self, rows):
        self._rows = list(rows)
        self._filters = {}

    def filter(self, *args, **kwargs):
        for clause in args:
            right = getattr(clause, "right", None)
            value = getattr(right, "value", None)
            left = getattr(clause, "left", None)
            column_name = getattr(left, "name", None)
            if column_name:
                self._filters[column_name] = value
        return self

    def all(self):
        rows = list(self._rows)
        for key, value in self._filters.items():
            rows = [row for row in rows if getattr(row, key, None) == value]
        return rows


class _FakeDeleteSession:
    def __init__(self, rows):
        self._rows = list(rows)
        self.deleted = []
        self.committed = False

    def query(self, entity, *args, **kwargs):
        return _FakeDeleteQuery(self._rows)

    def delete(self, record):
        self.deleted.append(record)

    def commit(self):
        self.committed = True


class HandleFormDeletionTests(unittest.TestCase):
    def test_delete_form_uses_optional_phonology_when_provided(self) -> None:
        created_at = "2026-06-01 10:00:00"
        user = SimpleNamespace(id=7, username="tester")
        matched = SimpleNamespace(
            user_id=7,
            簡稱="茶山增埗",
            音典分區="嶺南",
            經緯度="113.0,23.0",
            聲韻調="調值",
            特徵="陰平",
            值="55",
            說明="tone",
            created_at=created_at,
        )
        same_core_other_phonology = SimpleNamespace(
            user_id=7,
            簡稱="茶山增埗",
            音典分區="嶺南",
            經緯度="113.0,23.0",
            聲韻調="漢字",
            特徵="陰平",
            值="55",
            說明="char",
            created_at=created_at,
        )
        session = _FakeDeleteSession([matched, same_core_other_phonology])

        with patch(
            "app.service.user.submission.delete.class_mapper",
            side_effect=lambda cls: SimpleNamespace(columns=[SimpleNamespace(key=key) for key in [
                "簡稱", "音典分區", "經緯度", "聲韻調", "特徵", "值", "說明", "created_at", "user_id"
            ]]),
        ):
            result = handle_form_deletion(
                {
                    "location": "茶山增埗",
                    "phonology": "調值",
                    "feature": "陰平",
                    "value": "55",
                    "created_at": "2026-06-01T10:00:00",
                },
                user,
                session,
            )

        self.assertTrue(result["success"])
        self.assertEqual(session.deleted, [matched])
        self.assertTrue(session.committed)

    def test_delete_form_keeps_legacy_behavior_without_phonology(self) -> None:
        created_at = "2026-06-01 10:00:00"
        user = SimpleNamespace(id=7, username="tester")
        matched_a = SimpleNamespace(
            user_id=7,
            簡稱="茶山增埗",
            音典分區="嶺南",
            經緯度="113.0,23.0",
            聲韻調="調值",
            特徵="陰平",
            值="55",
            說明="tone",
            created_at=created_at,
        )
        matched_b = SimpleNamespace(
            user_id=7,
            簡稱="茶山增埗",
            音典分區="嶺南",
            經緯度="113.0,23.0",
            聲韻調="漢字",
            特徵="陰平",
            值="55",
            說明="char",
            created_at=created_at,
        )
        session = _FakeDeleteSession([matched_a, matched_b])

        with patch(
            "app.service.user.submission.delete.class_mapper",
            side_effect=lambda cls: SimpleNamespace(columns=[SimpleNamespace(key=key) for key in [
                "簡稱", "音典分區", "經緯度", "聲韻調", "特徵", "值", "說明", "created_at", "user_id"
            ]]),
        ):
            result = handle_form_deletion(
                {
                    "location": "茶山增埗",
                    "feature": "陰平",
                    "value": "55",
                    "created_at": "2026-06-01T10:00:00",
                },
                user,
                session,
            )

        self.assertTrue(result["success"])
        self.assertEqual(session.deleted, [matched_a, matched_b])
        self.assertTrue(session.committed)


if __name__ == "__main__":
    unittest.main()
