# app/tools/file_manager.py
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterable, Optional

from app.tools.config import (
    DEFAULT_ARTIFACT_CAPACITY_LIMITS,
    DEFAULT_CLEANUP_POLICIES,
    GLOBAL_CLEANUP_FALLBACK_SECONDS,
)


class FileManager:
    """
    通用文件管理器
    负责管理文件的存储、路径获取和清理
    """

    _TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")

    def __init__(self, base_dir: Optional[str] = None):
        """
        初始化文件管理器

        Args:
            base_dir: 文件存储基础目录。
                      优先级: 传入参数 > 环境变量 FILE_STORAGE_PATH > 系统临时目录
        """
        # 1. 优先使用传入的参数
        if base_dir:
            self.base_dir = Path(base_dir)
        # 2. 其次使用环境变量 (Docker 部署常用)
        elif os.getenv("FILE_STORAGE_PATH"):
            self.base_dir = Path(os.getenv("FILE_STORAGE_PATH"))
        # 3. 最后回退到系统临时目录
        else:
            self.base_dir = Path(tempfile.gettempdir()) / "fastapi_tools"

        # 确保基础目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_policies = dict(DEFAULT_CLEANUP_POLICIES)
        print(f"[FileManager] Storage Path: {self.base_dir.resolve()}")

    def _normalize_task_id(self, task_id: str) -> str:
        safe_task_id = (task_id or "").strip()
        if not self._TASK_ID_PATTERN.fullmatch(safe_task_id):
            raise ValueError("Invalid task_id format")
        return safe_task_id

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        safe_name = Path(filename or "").name.strip()
        if safe_name in {"", ".", ".."}:
            raise ValueError("Invalid filename")
        return safe_name

    def get_tool_dir(self, tool_name: str) -> Path:
        """
        获取工具对应的存储目录 (动态生成)
        例如 tool_name="check" -> /tmp/fastapi_tools/check
        """
        # 自动拼接路径，不再需要维护字典映射
        tool_dir = self.base_dir / tool_name

        # 确保该工具的目录存在
        if not tool_dir.exists():
            tool_dir.mkdir(parents=True, exist_ok=True)

        return tool_dir

    def get_task_json_path(self, task_id: str, tool_name: str) -> Path:
        """
        获取任务状态文件路径。
        默认不会主动创建目录，供清理扫描与只读查询使用。
        """
        safe_task_id = self._normalize_task_id(task_id)
        return self.base_dir / tool_name / safe_task_id / "task_info.json"

    def get_task_dir(self, task_id: str, tool_name: str) -> Path:
        """
        获取任务专属目录
        结构: base_dir / tool_name / task_id
        """
        safe_task_id = self._normalize_task_id(task_id)
        task_dir = self.get_tool_dir(tool_name) / safe_task_id
        # 确保任务目录存在
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def save_upload_file(self, task_id: str, tool_name: str,
                         file: BinaryIO, filename: str) -> Path:
        """保存上传的文件"""
        task_dir = self.get_task_dir(task_id, tool_name)

        safe_name = self._normalize_filename(filename)
        task_dir_resolved = task_dir.resolve()
        file_path = (task_dir_resolved / safe_name).resolve()
        if file_path.parent != task_dir_resolved:
            raise ValueError("Invalid upload path")
        try:
            # 指针归零，防止读取过的文件保存为空
            file.seek(0)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file, f)
        except Exception as e:
            print(f"[FileManager] Save failed: {e}")
            raise e

        return file_path

    def get_file_path(self, task_id: str, tool_name: str, filename: str) -> Optional[Path]:
        """获取文件路径"""
        # 注意：这里不需要 mkdir，只是查找
        tool_dir = self.base_dir / tool_name
        safe_task_id = self._normalize_task_id(task_id)
        safe_name = self._normalize_filename(filename)
        file_path = tool_dir / safe_task_id / safe_name
        return file_path if file_path.exists() else None

    def delete_task_files(self, task_id: str, tool_name: str):
        """删除任务相关的所有文件"""
        tool_dir = self.base_dir / tool_name
        safe_task_id = self._normalize_task_id(task_id)
        task_dir = tool_dir / safe_task_id
        if task_dir.exists():
            try:
                shutil.rmtree(task_dir)
            except Exception as e:
                print(f"[FileManager] Delete failed: {e}")

    def list_task_files(self, task_id: str, tool_name: str) -> list[str]:
        """列出任务目录下的所有文件"""
        tool_dir = self.base_dir / tool_name
        safe_task_id = self._normalize_task_id(task_id)
        task_dir = tool_dir / safe_task_id

        if not task_dir.exists():
            return []

        return [f.name for f in task_dir.iterdir() if f.is_file()]

    @staticmethod
    def _load_json(path: Path) -> Optional[Dict[str, Any]]:
        try:
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return None

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _task_status_value(raw_status: Any) -> str:
        if hasattr(raw_status, "value"):
            return str(raw_status.value)
        return str(raw_status or "")

    def _iter_task_policy_tool_dirs(self) -> Iterable[Path]:
        seen = set()
        for policy in self.cleanup_policies.values():
            if policy.get("object_type") != "task":
                continue
            tool_name = str(policy.get("tool_name") or "")
            if not tool_name or tool_name in seen:
                continue
            seen.add(tool_name)
            tool_dir = self.base_dir / tool_name
            if tool_dir.exists() and tool_dir.is_dir():
                yield tool_dir

    @staticmethod
    def _extract_artifact_meta(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        artifact = payload.get("artifact")
        if isinstance(artifact, dict) and artifact.get("object_type") == "artifact":
            return artifact
        metadata = payload.get("metadata")
        if isinstance(metadata, dict) and metadata.get("object_type") == "artifact":
            return metadata
        return None

    def _artifact_root(self, tool_name: str) -> Path:
        return self.base_dir / tool_name / "_artifacts"

    def _artifact_file_paths(self, tool_name: str, relative_paths: Iterable[str]) -> list[Path]:
        artifact_root = self._artifact_root(tool_name).resolve()
        file_paths: list[Path] = []
        for relative_path in relative_paths:
            candidate = (artifact_root / relative_path).resolve()
            try:
                candidate.relative_to(artifact_root)
            except ValueError:
                continue
            file_paths.append(candidate)
        return file_paths

    def _artifact_size_bytes(self, meta: Dict[str, Any], tool_name: str) -> int:
        declared = self._coerce_float(meta.get("size_bytes"))
        if declared is not None and declared >= 0:
            return int(declared)
        total = 0
        for path in self._artifact_file_paths(tool_name, meta.get("files") or []):
            if path.exists() and path.is_file():
                total += path.stat().st_size
        return total

    def _delete_artifact_files(self, tool_name: str, relative_paths: Iterable[str]) -> int:
        deleted = 0
        for path in self._artifact_file_paths(tool_name, relative_paths):
            try:
                if path.exists():
                    path.unlink()
                    deleted += 1
            except Exception as exc:
                print(f"[Cleanup] Error deleting artifact file {path}: {exc}")
        return deleted

    def _prune_empty_parents(self, path: Path, stop_at: Path) -> None:
        current = path.parent
        stop_at = stop_at.resolve()
        while current.exists():
            try:
                current.relative_to(stop_at)
            except ValueError:
                break
            if current == stop_at:
                break
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

    def _delete_artifact_entry(self, tool_name: str, meta: Dict[str, Any]) -> int:
        deleted = self._delete_artifact_files(tool_name, meta.get("files") or [])
        artifact_root = self._artifact_root(tool_name)
        for relative_path in meta.get("files") or []:
            candidate = artifact_root / relative_path
            self._prune_empty_parents(candidate, artifact_root)
        return deleted

    def _delete_directory(self, path: Path) -> bool:
        try:
            if path.exists():
                shutil.rmtree(path)
                return True
        except Exception as exc:
            print(f"[Cleanup] Error deleting {path}: {exc}")
        return False

    def _remove_task_dir(self, task_dir: Path) -> bool:
        return self._delete_directory(task_dir)

    def _should_fallback_delete(self, *, last_used_at: Optional[float], updated_at: Optional[float], mtime: Optional[float], now_ts: float, fallback_max_age_seconds: int) -> bool:
        for candidate in (last_used_at, updated_at, mtime):
            if candidate is None:
                continue
            if now_ts - candidate >= fallback_max_age_seconds:
                return True
            return False
        return False

    def _sweep_task_objects(
        self,
        *,
        now_ts: float,
        fallback_max_age_seconds: int,
    ) -> Dict[str, int]:
        tasks_deleted = 0
        fallback_deleted = 0

        for tool_dir in self._iter_task_policy_tool_dirs():
            for task_dir in tool_dir.iterdir():
                if not task_dir.is_dir():
                    continue
                if task_dir.name.startswith(".") or task_dir.name == "_artifacts":
                    continue

                task_info_path = task_dir / "task_info.json"
                dir_mtime = self._coerce_float(task_dir.stat().st_mtime)
                if not task_info_path.exists():
                    if self._should_fallback_delete(
                        last_used_at=None,
                        updated_at=None,
                        mtime=dir_mtime,
                        now_ts=now_ts,
                        fallback_max_age_seconds=fallback_max_age_seconds,
                    ):
                        if self._remove_task_dir(task_dir):
                            fallback_deleted += 1
                    continue

                task_info = self._load_json(task_info_path)
                if not task_info:
                    if self._should_fallback_delete(
                        last_used_at=None,
                        updated_at=None,
                        mtime=dir_mtime,
                        now_ts=now_ts,
                        fallback_max_age_seconds=fallback_max_age_seconds,
                    ):
                        if self._remove_task_dir(task_dir):
                            fallback_deleted += 1
                    continue

                cleanup = ((task_info.get("data") or {}).get("cleanup") or {})
                status = self._task_status_value(task_info.get("status"))
                if isinstance(cleanup, dict) and cleanup.get("object_type") == "task":
                    expires_at = self._coerce_float(cleanup.get("expires_at"))
                    armed = bool(cleanup.get("armed"))
                    terminal = bool(cleanup.get("terminal"))
                    if status not in {"pending", "processing"} and armed and terminal and expires_at is not None and expires_at <= now_ts:
                        if self._remove_task_dir(task_dir):
                            tasks_deleted += 1
                    continue

                if self._should_fallback_delete(
                    last_used_at=self._coerce_float(cleanup.get("last_used_at")) if isinstance(cleanup, dict) else None,
                    updated_at=self._coerce_float(task_info.get("updated_at")),
                    mtime=dir_mtime,
                    now_ts=now_ts,
                    fallback_max_age_seconds=fallback_max_age_seconds,
                ):
                    if self._remove_task_dir(task_dir):
                        fallback_deleted += 1

        return {
            "tasks_deleted": tasks_deleted,
            "fallback_deleted": fallback_deleted,
        }

    def _iter_artifact_manifests(self) -> Iterable[tuple[Path, Dict[str, Any], Dict[str, Any]]]:
        for policy in self.cleanup_policies.values():
            if policy.get("object_type") != "artifact":
                continue
            tool_name = str(policy.get("tool_name") or "")
            scan_glob = str(policy.get("scan_glob") or "")
            if not tool_name or not scan_glob:
                continue
            tool_dir = self.base_dir / tool_name
            if not tool_dir.exists():
                continue
            for manifest_path in tool_dir.glob(scan_glob):
                if not manifest_path.is_file() or manifest_path.name.startswith("."):
                    continue
                payload = self._load_json(manifest_path)
                if not payload:
                    yield manifest_path, {}, policy
                    continue
                meta = self._extract_artifact_meta(payload)
                if not meta:
                    yield manifest_path, {}, policy
                    continue
                yield manifest_path, meta, policy

    def _sweep_artifact_objects(
        self,
        *,
        now_ts: float,
        fallback_max_age_seconds: int,
    ) -> Dict[str, int]:
        artifacts_deleted = 0
        fallback_deleted = 0

        for manifest_path, meta, policy in self._iter_artifact_manifests():
            tool_name = str(policy.get("tool_name") or "")
            if not meta:
                manifest_mtime = self._coerce_float(manifest_path.stat().st_mtime)
                if self._should_fallback_delete(
                    last_used_at=None,
                    updated_at=None,
                    mtime=manifest_mtime,
                    now_ts=now_ts,
                    fallback_max_age_seconds=fallback_max_age_seconds,
                ):
                    try:
                        manifest_path.unlink(missing_ok=True)
                        fallback_deleted += 1
                    except Exception as exc:
                        print(f"[Cleanup] Error deleting invalid manifest {manifest_path}: {exc}")
                continue

            expires_at = self._coerce_float(meta.get("expires_at"))
            last_used_at = self._coerce_float(meta.get("last_used_at"))
            expired = expires_at is not None and expires_at <= now_ts
            stale = last_used_at is not None and now_ts - last_used_at >= fallback_max_age_seconds
            if expired or stale:
                deleted = self._delete_artifact_entry(tool_name, meta)
                if deleted > 0 or manifest_path.exists():
                    artifacts_deleted += 1
                continue

        return {
            "artifacts_deleted": artifacts_deleted,
            "fallback_deleted": fallback_deleted,
        }

    def _enforce_capacity_limits(
        self,
        *,
        now_ts: float,
        artifact_capacity_limits: Optional[Dict[str, int]] = None,
    ) -> Dict[str, int]:
        limits = dict(DEFAULT_ARTIFACT_CAPACITY_LIMITS)
        if artifact_capacity_limits:
            limits.update(artifact_capacity_limits)

        grouped: Dict[str, list[tuple[float, int, Path, Dict[str, Any], Dict[str, Any]]]] = {}
        totals: Dict[str, int] = {}

        for manifest_path, meta, policy in self._iter_artifact_manifests():
            if not meta:
                continue
            capacity_group = policy.get("capacity_group")
            if not capacity_group:
                continue
            tool_name = str(policy.get("tool_name") or "")
            size_bytes = self._artifact_size_bytes(meta, tool_name)
            last_used_at = self._coerce_float(meta.get("last_used_at")) or 0.0
            grouped.setdefault(capacity_group, []).append((last_used_at, size_bytes, manifest_path, meta, policy))
            totals[capacity_group] = totals.get(capacity_group, 0) + size_bytes

        capacity_deleted = 0
        for capacity_group, items in grouped.items():
            limit = int(limits.get(capacity_group, 0) or 0)
            if limit <= 0:
                continue
            total = totals.get(capacity_group, 0)
            if total <= limit:
                continue
            for _, size_bytes, manifest_path, meta, policy in sorted(items, key=lambda item: (item[0], item[2].name)):
                tool_name = str(policy.get("tool_name") or "")
                deleted = self._delete_artifact_entry(tool_name, meta)
                if deleted > 0 or manifest_path.exists():
                    capacity_deleted += 1
                total -= max(size_bytes, 0)
                if total <= limit:
                    break

        return {
            "capacity_deleted": capacity_deleted,
        }

    def _cleanup_fallback_orphans(
        self,
        *,
        now_ts: float,
        fallback_max_age_seconds: int,
    ) -> Dict[str, int]:
        fallback_deleted = 0
        cluster_artifact_root = self.base_dir / "cluster" / "_artifacts"
        if cluster_artifact_root.exists():
            for path in cluster_artifact_root.rglob("*"):
                if path.is_dir():
                    continue
                if path.name.endswith(".json"):
                    continue
                companion_manifest = path.with_suffix(".json")
                if companion_manifest.exists():
                    continue
                mtime = self._coerce_float(path.stat().st_mtime)
                if not self._should_fallback_delete(
                    last_used_at=None,
                    updated_at=None,
                    mtime=mtime,
                    now_ts=now_ts,
                    fallback_max_age_seconds=fallback_max_age_seconds,
                ):
                    continue
                try:
                    path.unlink(missing_ok=True)
                    fallback_deleted += 1
                except Exception as exc:
                    print(f"[Cleanup] Error deleting orphan artifact {path}: {exc}")
        return {
            "fallback_deleted": fallback_deleted,
        }

    def cleanup_once(
        self,
        *,
        now_ts: Optional[float] = None,
        fallback_max_age_seconds: int = GLOBAL_CLEANUP_FALLBACK_SECONDS,
        artifact_capacity_limits: Optional[Dict[str, int]] = None,
    ) -> Dict[str, int]:
        current_time = float(now_ts if now_ts is not None else time.time())
        result = {
            "tasks_deleted": 0,
            "artifacts_deleted": 0,
            "capacity_deleted": 0,
            "fallback_deleted": 0,
            "total_deleted": 0,
        }

        if not self.base_dir.exists():
            return result

        task_result = self._sweep_task_objects(
            now_ts=current_time,
            fallback_max_age_seconds=fallback_max_age_seconds,
        )
        artifact_result = self._sweep_artifact_objects(
            now_ts=current_time,
            fallback_max_age_seconds=fallback_max_age_seconds,
        )
        capacity_result = self._enforce_capacity_limits(
            now_ts=current_time,
            artifact_capacity_limits=artifact_capacity_limits,
        )
        fallback_result = self._cleanup_fallback_orphans(
            now_ts=current_time,
            fallback_max_age_seconds=fallback_max_age_seconds,
        )

        result["tasks_deleted"] = task_result["tasks_deleted"]
        result["artifacts_deleted"] = artifact_result["artifacts_deleted"]
        result["capacity_deleted"] = capacity_result["capacity_deleted"]
        result["fallback_deleted"] = (
            task_result["fallback_deleted"]
            + artifact_result["fallback_deleted"]
            + fallback_result["fallback_deleted"]
        )
        result["total_deleted"] = (
            result["tasks_deleted"]
            + result["artifacts_deleted"]
            + result["capacity_deleted"]
            + result["fallback_deleted"]
        )
        return result

    def cleanup_old_files(self, max_age_hours: int = 24):
        """
        兼容旧接口。
        现在统一委托给新的 policy-based cleanup 入口。
        """
        summary = self.cleanup_once(
            fallback_max_age_seconds=int(max_age_hours * 3600),
        )
        return int(summary["total_deleted"])


# 全局文件管理器实例
file_manager = FileManager()
