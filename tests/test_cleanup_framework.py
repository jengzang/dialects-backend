import json
import tempfile
import time
import unittest
from pathlib import Path

from app.tools.file_manager import FileManager


class CleanupFrameworkTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tempdir.name)
        self.file_manager = FileManager(base_dir=str(self.base_dir))
        self.now = 1_710_000_000.0

    def tearDown(self) -> None:
        self._tempdir.cleanup()

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_task_info(
        self,
        *,
        tool_name: str,
        task_id: str,
        status: str = "completed",
        updated_at: float | None = None,
        cleanup: dict | None = None,
    ) -> Path:
        task_dir = self.base_dir / tool_name / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        task_info = {
            "task_id": task_id,
            "tool_name": tool_name,
            "status": status,
            "progress": 100.0,
            "message": "",
            "created_at": self.now - 10,
            "updated_at": updated_at if updated_at is not None else self.now,
            "data": {},
            "error": None,
        }
        if cleanup is not None:
            task_info["data"]["cleanup"] = cleanup
        self._write_json(task_dir / "task_info.json", task_info)
        return task_dir

    def _write_artifact_manifest(
        self,
        *,
        policy_key: str,
        stage: str,
        artifact_key: str,
        expires_at: float,
        last_used_at: float,
        size_bytes: int,
        extra_files: list[tuple[str, bytes]],
    ) -> Path:
        artifact_root = self.base_dir / "cluster" / "_artifacts"
        stage_dir = artifact_root / stage
        stage_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = stage_dir / f"{artifact_key}.json"
        files = [f"{stage}/{artifact_key}.json"]
        for rel_path, content in extra_files:
            path = artifact_root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            files.append(rel_path)

        manifest = {
            "artifact": {
                "version": 1,
                "object_type": "artifact",
                "policy_key": policy_key,
                "artifact_type": stage,
                "artifact_key": artifact_key,
                "files": files,
                "size_bytes": size_bytes,
                "created_at": self.now - 100,
                "updated_at": self.now - 50,
                "last_used_at": last_used_at,
                "expires_at": expires_at,
            }
        }
        self._write_json(manifest_path, manifest)
        return manifest_path

    def test_cleanup_once_removes_expired_terminal_task(self) -> None:
        task_dir = self._write_task_info(
            tool_name="check",
            task_id="check_expired",
            cleanup={
                "version": 1,
                "object_type": "task",
                "policy_key": "check_workspace",
                "armed": True,
                "terminal": True,
                "expires_at": self.now - 1,
                "last_used_at": self.now - 1800,
                "last_reason": "save_changes",
            },
        )

        result = self.file_manager.cleanup_once(now_ts=self.now)

        self.assertFalse(task_dir.exists())
        self.assertGreaterEqual(result["tasks_deleted"], 1)

    def test_cleanup_once_keeps_processing_task_even_if_expired(self) -> None:
        task_dir = self._write_task_info(
            tool_name="merge",
            task_id="merge_processing",
            status="processing",
            cleanup={
                "version": 1,
                "object_type": "task",
                "policy_key": "merge_result",
                "armed": True,
                "terminal": False,
                "expires_at": self.now - 1,
                "last_used_at": self.now - 7200,
                "last_reason": "execute_started",
            },
        )

        result = self.file_manager.cleanup_once(now_ts=self.now)

        self.assertTrue(task_dir.exists())
        self.assertEqual(result["tasks_deleted"], 0)

    def test_cleanup_once_removes_expired_artifact_and_its_payload_files(self) -> None:
        manifest_path = self._write_artifact_manifest(
            policy_key="cluster_prepare",
            stage="prepare",
            artifact_key="prepare_hash_1",
            expires_at=self.now - 1,
            last_used_at=self.now - 7200,
            size_bytes=1234,
            extra_files=[("prepare/prepare_hash_1.npz", b"payload")],
        )
        payload_path = self.base_dir / "cluster" / "_artifacts" / "prepare" / "prepare_hash_1.npz"

        result = self.file_manager.cleanup_once(now_ts=self.now)

        self.assertFalse(manifest_path.exists())
        self.assertFalse(payload_path.exists())
        self.assertGreaterEqual(result["artifacts_deleted"], 1)

    def test_cleanup_once_enforces_cluster_artifact_capacity_by_last_use(self) -> None:
        old_manifest = self._write_artifact_manifest(
            policy_key="cluster_result",
            stage="result",
            artifact_key="old_result",
            expires_at=self.now + 3600,
            last_used_at=self.now - 5000,
            size_bytes=700,
            extra_files=[],
        )
        new_manifest = self._write_artifact_manifest(
            policy_key="cluster_result",
            stage="result",
            artifact_key="new_result",
            expires_at=self.now + 3600,
            last_used_at=self.now - 100,
            size_bytes=500,
            extra_files=[],
        )

        result = self.file_manager.cleanup_once(
            now_ts=self.now,
            artifact_capacity_limits={"cluster_artifacts": 1024},
        )

        self.assertFalse(old_manifest.exists())
        self.assertTrue(new_manifest.exists())
        self.assertGreaterEqual(result["capacity_deleted"], 1)

    def test_cleanup_once_falls_back_to_updated_at_for_legacy_task(self) -> None:
        task_dir = self._write_task_info(
            tool_name="jyut2ipa",
            task_id="jyut2ipa_legacy",
            updated_at=self.now - (12 * 3600 + 10),
            cleanup=None,
        )

        result = self.file_manager.cleanup_once(now_ts=self.now)

        self.assertFalse(task_dir.exists())
        self.assertGreaterEqual(result["fallback_deleted"], 1)


if __name__ == "__main__":
    unittest.main()
