# app/tools/file_manager.py
"""
文件管理系统：管理上传文件的存储、读取和清理
"""

import os
import shutil
from pathlib import Path
from typing import Optional, BinaryIO
import tempfile
from datetime import datetime


class FileManager:
    """文件管理器"""

    def __init__(self, base_dir: Optional[str] = None):
        """
        初始化文件管理器

        Args:
            base_dir: 文件存储基础目录，默认使用系统临时目录
        """
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(tempfile.gettempdir()) / "fastapi_tools"

        # 创建基础目录
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 创建各工具的子目录
        self.check_dir = self.base_dir / "check"
        self.jyut2ipa_dir = self.base_dir / "jyut2ipa"
        self.merge_dir = self.base_dir / "merge"

        for dir_path in [self.check_dir, self.jyut2ipa_dir, self.merge_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def get_tool_dir(self, tool_name: str) -> Path:
        """获取工具对应的存储目录"""
        tool_dirs = {
            "check": self.check_dir,
            "jyut2ipa": self.jyut2ipa_dir,
            "merge": self.merge_dir
        }
        return tool_dirs.get(tool_name, self.base_dir)

    def save_upload_file(self, task_id: str, tool_name: str,
                         file: BinaryIO, filename: str) -> Path:
        """
        保存上传的文件

        Args:
            task_id: 任务ID
            tool_name: 工具名称
            file: 文件对象
            filename: 原始文件名

        Returns:
            保存后的文件路径
        """
        # 创建任务专属目录
        task_dir = self.get_tool_dir(tool_name) / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # 保存文件
        file_path = task_dir / filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file, f)

        return file_path

    def get_file_path(self, task_id: str, tool_name: str, filename: str) -> Optional[Path]:
        """
        获取文件路径

        Args:
            task_id: 任务ID
            tool_name: 工具名称
            filename: 文件名

        Returns:
            文件路径，如果不存在则返回None
        """
        file_path = self.get_tool_dir(tool_name) / task_id / filename
        return file_path if file_path.exists() else None

    def delete_task_files(self, task_id: str, tool_name: str):
        """
        删除任务相关的所有文件

        Args:
            task_id: 任务ID
            tool_name: 工具名称
        """
        task_dir = self.get_tool_dir(tool_name) / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir)

    def cleanup_old_files(self, max_age_hours: int = 24):
        """
        清理旧文件（默认24小时）

        Args:
            max_age_hours: 文件最大保留时间（小时）

        Returns:
            删除的文件数量
        """
        import time
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        deleted_count = 0

        for tool_dir in [self.check_dir, self.jyut2ipa_dir, self.merge_dir]:
            if not tool_dir.exists():
                continue

            for task_dir in tool_dir.iterdir():
                if not task_dir.is_dir():
                    continue

                # 检查目录的最后修改时间
                dir_mtime = task_dir.stat().st_mtime
                if current_time - dir_mtime > max_age_seconds:
                    shutil.rmtree(task_dir)
                    deleted_count += 1

        return deleted_count

    def get_task_dir(self, task_id: str, tool_name: str) -> Path:
        """
        获取任务目录路径

        Args:
            task_id: 任务ID
            tool_name: 工具名称

        Returns:
            任务目录路径
        """
        task_dir = self.get_tool_dir(tool_name) / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def list_task_files(self, task_id: str, tool_name: str) -> list[str]:
        """
        列出任务目录下的所有文件

        Args:
            task_id: 任务ID
            tool_name: 工具名称

        Returns:
            文件名列表
        """
        task_dir = self.get_tool_dir(tool_name) / task_id
        if not task_dir.exists():
            return []

        return [f.name for f in task_dir.iterdir() if f.is_file()]


# 全局文件管理器实例
file_manager = FileManager()
