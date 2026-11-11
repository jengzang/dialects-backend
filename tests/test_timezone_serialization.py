import os
import time
from datetime import datetime, timezone

from app.tools.praat.utils.job_utils import update_job_status
from app.villagesML.metadata.stats import _format_file_timestamp_utc


def test_praat_job_updates_are_serialized_as_utc(monkeypatch):
    if not hasattr(time, "tzset"):
        return

    original_timezone = os.environ.get("TZ")
    try:
        monkeypatch.setenv("TZ", "Asia/Shanghai")
        time.tzset()

        task = {"data": {"jobs": [{"job_id": "task_job_1"}]}}

        class TaskManager:
            def get_task(self, _task_id):
                return task

            def update_task(self, _task_id, **_kwargs):
                pass

        update_job_status(TaskManager(), "task", "task_job_1", status="running")

        updated_at = datetime.fromisoformat(task["data"]["jobs"][0]["updated_at"])
        assert updated_at.tzinfo is not None
        assert updated_at.utcoffset().total_seconds() == 0
    finally:
        if original_timezone is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", original_timezone)
        time.tzset()


def test_villagesml_file_timestamp_is_utc_independent_of_process_timezone(monkeypatch):
    if not hasattr(time, "tzset"):
        return

    original_timezone = os.environ.get("TZ")
    try:
        monkeypatch.setenv("TZ", "Asia/Shanghai")
        time.tzset()

        timestamp = 1794361945
        serialized = _format_file_timestamp_utc(timestamp)

        assert serialized == datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    finally:
        if original_timezone is None:
            monkeypatch.delenv("TZ", raising=False)
        else:
            monkeypatch.setenv("TZ", original_timezone)
        time.tzset()
