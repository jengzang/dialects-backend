import asyncio
import io
import time
import unittest
from datetime import datetime, UTC
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
from fastapi import BackgroundTasks, UploadFile

from app.tools.check.check_routes import get_check_progress, start_analyze_async
from app.tools.merge.merge_routes import get_merge_progress
from app.tools.merge.merge_routes import upload_reference
from app.tools.jyut2ipa.jyut2ipa_routes import get_progress as get_jyut2ipa_progress
from app.tools.jyut2ipa.jyut2ipa_routes import upload_file as upload_jyut2ipa_file
from app.tools.praat.routes import get_job_status


class ToolsProgressContractTests(unittest.TestCase):
    def test_praat_job_status_scales_fractional_progress_to_percent(self):
        now = datetime.now(UTC).isoformat()
        task = {
            "data": {
                "jobs": [
                    {
                        "job_id": "praat_task_job_1",
                        "status": "running",
                        "progress": 0.5,
                        "stage": "pitch",
                        "error": None,
                        "created_at": now,
                        "updated_at": now,
                    }
                ]
            }
        }

        with patch("app.tools.praat.routes.task_manager.get_task", return_value=task):
            result = asyncio.run(get_job_status("praat_task_job_1"))

        self.assertEqual(result["progress"], 50.0)

    def test_praat_job_status_keeps_percent_progress_unchanged(self):
        now = datetime.now(UTC).isoformat()
        task = {
            "data": {
                "jobs": [
                    {
                        "job_id": "praat_task_job_1",
                        "status": "running",
                        "progress": 50.0,
                        "stage": "pitch",
                        "error": None,
                        "created_at": now,
                        "updated_at": now,
                    }
                ]
            }
        }

        with patch("app.tools.praat.routes.task_manager.get_task", return_value=task):
            result = asyncio.run(get_job_status("praat_task_job_1"))

        self.assertEqual(result["progress"], 50.0)

    def test_merge_progress_exposes_liveness_fields(self):
        task = {
            "status": "processing",
            "progress": 25.0,
            "message": "正在合并文件",
            "stage": "merging",
            "updated_at": time.time(),
        }

        with patch("app.tools.merge.merge_routes.task_manager.get_task", return_value=task):
            result = asyncio.run(get_merge_progress("merge_task"))

        payload = result.model_dump()
        self.assertEqual(payload["stage"], "merging")
        self.assertIsNotNone(payload["updated_at"])

    def test_jyut2ipa_progress_exposes_liveness_fields(self):
        task = {
            "status": "processing",
            "progress": 42.0,
            "message": "正在处理第 42/100 行",
            "stage": "processing_rows",
            "updated_at": time.time(),
        }

        with patch("app.tools.jyut2ipa.jyut2ipa_routes.task_manager.get_task", return_value=task):
            result = asyncio.run(get_jyut2ipa_progress("jyut2ipa_task"))

        payload = result.model_dump()
        self.assertEqual(payload["stage"], "processing_rows")
        self.assertIsNotNone(payload["updated_at"])

    def test_merge_progress_times_out_stale_processing_task(self):
        stale_task = {
            "task_id": "merge_task",
            "status": "processing",
            "progress": 30.0,
            "message": "正在合并文件",
            "stage": "merging",
            "updated_at": time.time() - 3600,
        }

        def update_task_side_effect(task_id, **kwargs):
            stale_task.update(kwargs)

        with patch("app.tools.merge.merge_routes.task_manager.get_task", return_value=stale_task), patch(
            "app.tools.merge.merge_routes.task_manager.update_task",
            side_effect=update_task_side_effect,
        ):
            result = asyncio.run(get_merge_progress("merge_task"))

        self.assertEqual(result.status, "failed")
        self.assertIn("timeout", (stale_task.get("error") or "").lower())

    def test_merge_reference_upload_keeps_progress_at_zero_until_execute(self):
        update_calls = []

        def record_update(task_id, **kwargs):
            update_calls.append(kwargs)

        upload = UploadFile(filename="reference.xlsx", file=io.BytesIO(b"fake"))
        with patch("app.tools.merge.merge_routes.task_manager.create_task", return_value="merge_task"), patch(
            "app.tools.merge.merge_routes.file_manager.save_upload_file",
            return_value=Path("/tmp/reference.xlsx"),
        ), patch(
            "app.tools.merge.merge_routes.load_reference_file",
            return_value=["甲", "乙"],
        ), patch(
            "app.tools.merge.merge_routes.task_manager.update_task",
            side_effect=record_update,
        ), patch("app.tools.merge.merge_routes._touch_merge_cleanup"):
            asyncio.run(upload_reference(upload))

        ready_update = update_calls[-1]
        self.assertEqual(ready_update["status"], "pending")
        self.assertEqual(ready_update["progress"], 0.0)
        self.assertEqual(ready_update["stage"], "reference_ready")

    def test_jyut2ipa_upload_keeps_progress_at_zero_until_processing(self):
        update_calls = []

        def record_update(task_id, **kwargs):
            update_calls.append(kwargs)

        upload = UploadFile(filename="input.xlsx", file=io.BytesIO(b"fake"))
        with patch("app.tools.jyut2ipa.jyut2ipa_routes.task_manager.create_task", return_value="jyut_task"), patch(
            "app.tools.jyut2ipa.jyut2ipa_routes.file_manager.save_upload_file",
            return_value=Path("/tmp/input.xlsx"),
        ), patch(
            "app.tools.jyut2ipa.jyut2ipa_routes.pd.read_excel",
            return_value=pd.DataFrame({"粤拼": ["si1", "jyut6"]}),
        ), patch(
            "app.tools.jyut2ipa.jyut2ipa_routes.task_manager.update_task",
            side_effect=record_update,
        ), patch("app.tools.jyut2ipa.jyut2ipa_routes._touch_jyut2ipa_cleanup"):
            asyncio.run(upload_jyut2ipa_file(upload))

        ready_update = update_calls[-1]
        self.assertEqual(ready_update["status"], "pending")
        self.assertEqual(ready_update["progress"], 0.0)
        self.assertEqual(ready_update["stage"], "ready")

    def test_praat_job_status_times_out_stale_job(self):
        old = datetime(2020, 1, 1, tzinfo=UTC).isoformat()
        task = {
            "data": {
                "jobs": [
                    {
                        "job_id": "praat_task_job_1",
                        "status": "running",
                        "progress": 0.5,
                        "stage": "pitch",
                        "error": None,
                        "created_at": old,
                        "updated_at": old,
                    }
                ]
            }
        }

        def mutate_job_status(_task_manager, _task_id, job_id, **updates):
            for job in task["data"]["jobs"]:
                if job["job_id"] == job_id:
                    job.update(updates)
                    job["updated_at"] = datetime.now(UTC).isoformat()

        with patch("app.tools.praat.routes.task_manager.get_task", return_value=task), patch(
            "app.tools.praat.routes.update_job_status",
            side_effect=mutate_job_status,
        ):
            result = asyncio.run(get_job_status("praat_task_job_1"))

        self.assertEqual(result["status"], "error")
        self.assertIn("timeout", result["error"]["message"].lower())

    def test_check_async_analyze_start_returns_pollable_task(self):
        task = {
            "task_id": "check_task",
            "status": "pending",
            "progress": 0.0,
            "message": "文件上传成功",
            "updated_at": time.time(),
            "data": {},
        }

        def mutate_task(task_id, **kwargs):
            task.update(kwargs)

        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "input.xlsx"
            file_path.write_bytes(b"placeholder")
            task["data"]["file_path"] = str(file_path)

            background_tasks = BackgroundTasks()
            with patch("app.tools.check.check_routes.task_manager.get_task", return_value=task), patch(
                "app.tools.check.check_routes.task_manager.update_task",
                side_effect=mutate_task,
            ):
                result = asyncio.run(start_analyze_async("check_task", background_tasks))

        self.assertEqual(result.status, "processing")
        self.assertEqual(result.progress, 0.0)
        self.assertEqual(result.stage, "queued")
        self.assertEqual(len(background_tasks.tasks), 1)

    def test_check_progress_returns_analysis_result_when_completed(self):
        task = {
            "task_id": "check_task",
            "status": "completed",
            "progress": 100.0,
            "message": "分析完成，发现2个错误",
            "stage": "completed",
            "updated_at": time.time(),
            "data": {
                "analysis_result": {
                    "task_id": "check_task",
                    "total_rows": 10,
                    "error_count": 2,
                    "errors": [
                        {
                            "row": 2,
                            "error_type": "invalidIpa",
                            "field": "ipa",
                            "value": "bad",
                            "message": "音标格式异常",
                        }
                    ],
                    "error_stats": {"invalidIpa": 2},
                }
            },
        }

        with patch("app.tools.check.check_routes.task_manager.get_task", return_value=task):
            result = asyncio.run(get_check_progress("check_task"))

        self.assertIsNotNone(result.analysis_result)
        self.assertEqual(result.analysis_result.task_id, "check_task")
        self.assertEqual(result.analysis_result.error_count, 2)


if __name__ == "__main__":
    unittest.main()
