"""
cluster 任务创建接口返回的轻量 schema。

注意这里不是最终聚类结果，而是“任务已创建 / 已命中缓存”的即时回执。
最终结果仍然通过 `/jobs/{task_id}/result` 拉取。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ClusterJobCreateResponse(BaseModel):
    """创建任务后返回给前端的最小任务摘要。"""
    task_id: str
    status: str
    progress: float
    message: str
    summary: Optional[dict] = None
