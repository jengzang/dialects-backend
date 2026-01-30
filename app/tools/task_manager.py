# app/tools/task_manager.py
"""
任务管理系统：管理文件上传任务的生命周期
"""
import json
import uuid
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import threading

from app.tools.file_manager import file_manager


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """任务数据类"""
    task_id: str
    tool_name: str  # check, jyut2ipa, merge
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0  # 0-100
    message: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)  # 存储任务相关数据
    error: Optional[str] = None

    def update(self, status: Optional[TaskStatus] = None,
               progress: Optional[float] = None,
               message: Optional[str] = None,
               data: Optional[Dict[str, Any]] = None,
               error: Optional[str] = None):
        """更新任务状态"""
        if status:
            self.status = status
        if progress is not None:
            self.progress = progress
        if message:
            self.message = message
        if data:
            self.data.update(data)
        if error:
            self.error = error
        self.updated_at = time.time()


class TaskManager:
    """
    基于文件的任务管理器
    完全去除了 self._tasks 内存字典，所有状态直接读写 JSON 文件
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def _get_task_json_path(self, task_id: str, tool_name: str) -> Path:
        """获取任务 JSON 文件的路径"""
        task_dir = file_manager.get_task_dir(task_id, tool_name)
        return task_dir / "task_info.json"

    def _parse_id(self, task_id: str) -> tuple[str, str]:
        """
        解析 ID，提取 tool_name
        ID 格式: "tool_name:uuid"
        """
        if "_" in task_id:
            tool_name, _ = task_id.split("_", 1)
            return tool_name, task_id
        else:
            # 兼容旧 ID 的兜底逻辑（如果还有旧数据的话）
            # 这里简单处理，如果找不到冒号，可能无法直接定位，需要遍历（略）
            # 建议新任务全部带前缀
            return "check", task_id

            # --- 核心 IO 方法 ---

    def _save_json(self, path: Path, data: Dict):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TaskManager] Save Error: {e}")

    def _load_json(self, path: Path) -> Optional[Dict]:
        try:
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # --- 公开 API ---

    def create_task(self, tool_name: str, initial_data: Optional[Dict[str, Any]] = None) -> str:
        """创建新任务并写入文件"""
        raw_uuid = str(uuid.uuid4())
        # 生成带前缀的 ID，方便后续快速定位
        task_id = f"{tool_name}_{raw_uuid}"

        # 构造字典（不再使用 Task 对象）
        task_info = {
            "task_id": task_id,
            "tool_name": tool_name,
            "status": TaskStatus.PENDING,
            "progress": 0.0,
            "message": "",
            "created_at": time.time(),
            "updated_at": time.time(),
            "data": initial_data or {},
            "error": None
        }

        # 直接写入硬盘
        json_path = self._get_task_json_path(task_id, tool_name)
        self._save_json(json_path, task_info)

        return task_id

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        返回字典 dict，不再是 Task 对象
        """
        # 1. 解析 ID 拿到 tool_name
        tool_name, _ = self._parse_id(task_id)

        # 2. 拼路径
        json_path = self._get_task_json_path(task_id, tool_name)

        # 3. 读文件
        return self._load_json(json_path)

    def update_task(self, task_id: str, **kwargs):
        """更新任务状态（读-改-写）"""
        tool_name, _ = self._parse_id(task_id)
        json_path = self._get_task_json_path(task_id, tool_name)

        # 加锁是为了防止极端的并发写入冲突（同一任务极短时间内被两次更新）
        with self._lock:
            # 1. 读取
            task_info = self._load_json(json_path)
            if not task_info:
                return

            # 2. 修改
            if "data" in kwargs and isinstance(kwargs["data"], dict):
                # 深度合并 data 字段
                if "data" not in task_info:
                    task_info["data"] = {}
                task_info["data"].update(kwargs.pop("data"))

            # 更新其他字段
            task_info.update(kwargs)
            task_info["updated_at"] = time.time()

            # 3. 写入
            self._save_json(json_path, task_info)

    def delete_task(self, task_id: str):
        """删除任务文件"""
        tool_name, _ = self._parse_id(task_id)
        # 调用 file_manager 删除整个文件夹
        file_manager.delete_task_files(task_id, tool_name)

    def cleanup_old_tasks(self, max_age_seconds: int = 3600):
        """
        清理过期任务
        直接调用 file_manager 的逻辑清理文件夹
        """
        # 换算成小时，因为你的 file_manager 默认是用小时计算的
        # 或者你可以修改 file_manager 让它支持秒
        hours = max_age_seconds / 3600.0
        return file_manager.cleanup_old_files(max_age_hours=hours)

    def get_all_tasks(self, tool_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        获取所有任务
        原理：遍历 file_manager.base_dir 下的所有 JSON 文件
        """
        tasks = {}
        base_dir = file_manager.base_dir

        if not base_dir.exists():
            return {}

        # 确定要搜索的工具目录列表
        if tool_name:
            target_tools = [tool_name]
        else:
            # 搜索 check, jyut2ipa, merge 等所有子目录
            target_tools = [d.name for d in base_dir.iterdir() if d.is_dir()]

        for tool in target_tools:
            tool_dir = base_dir / tool
            if not tool_dir.exists():
                continue

            # 遍历该工具下的每个 task_id 文件夹
            for task_dir in tool_dir.iterdir():
                json_path = task_dir / "task_info.json"

                # 如果存在 task_info.json，就读取它
                if json_path.exists():
                    task_data = self._load_json(json_path)
                    if task_data:
                        tasks[task_data['task_id']] = task_data

        return tasks

# 全局单例
task_manager = TaskManager()
