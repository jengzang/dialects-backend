# app/tools/task_manager.py
"""
任务管理系统：管理文件上传任务的生命周期
"""

import uuid
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import threading


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
    """任务管理器（单例模式）"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._initialized = True

    def create_task(self, tool_name: str, initial_data: Optional[Dict[str, Any]] = None) -> str:
        """
        创建新任务

        Args:
            tool_name: 工具名称（check, jyut2ipa, merge）
            initial_data: 初始数据

        Returns:
            task_id: 任务ID
        """
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            tool_name=tool_name,
            data=initial_data or {}
        )

        with self._lock:
            self._tasks[task_id] = task

        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        with self._lock:
            return self._tasks.get(task_id)

    def update_task(self, task_id: str, **kwargs):
        """更新任务状态"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.update(**kwargs)

    def delete_task(self, task_id: str):
        """删除任务"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]

    def cleanup_old_tasks(self, max_age_seconds: int = 3600):
        """清理过期任务（默认1小时）"""
        current_time = time.time()
        with self._lock:
            expired_tasks = [
                task_id for task_id, task in self._tasks.items()
                if current_time - task.updated_at > max_age_seconds
            ]
            for task_id in expired_tasks:
                del self._tasks[task_id]

        return len(expired_tasks)

    def get_all_tasks(self, tool_name: Optional[str] = None) -> Dict[str, Task]:
        """获取所有任务（可选按工具名筛选）"""
        with self._lock:
            if tool_name:
                return {
                    tid: task for tid, task in self._tasks.items()
                    if task.tool_name == tool_name
                }
            return self._tasks.copy()


# 全局任务管理器实例
task_manager = TaskManager()
