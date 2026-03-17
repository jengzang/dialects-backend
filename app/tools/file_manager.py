# app/tools/file_manager.py
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional, BinaryIO


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

    def cleanup_old_files(self, max_age_hours: int = 24):
        """
        清理旧文件
        逻辑：遍历 base_dir 下的所有工具目录，再检查其中的任务目录是否过期
        """
        import time
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        deleted_count = 0

        if not self.base_dir.exists():
            return 0

        # 1. 遍历所有工具目录 (check, jyut2ipa, merge, ...)
        for tool_dir in self.base_dir.iterdir():
            if not tool_dir.is_dir():
                continue

            # 2. 遍历该工具下的所有任务目录
            for task_dir in tool_dir.iterdir():
                if not task_dir.is_dir():
                    continue

                try:
                    # 检查最后修改时间
                    dir_mtime = task_dir.stat().st_mtime
                    if current_time - dir_mtime > max_age_seconds:
                        shutil.rmtree(task_dir)
                        deleted_count += 1
                        print(f"[Cleanup] Deleted expired task: {task_dir}")
                except Exception as e:
                    print(f"[Cleanup] Error deleting {task_dir}: {e}")

        return deleted_count


# 全局文件管理器实例
file_manager = FileManager()
