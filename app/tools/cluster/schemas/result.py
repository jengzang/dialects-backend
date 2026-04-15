"""
cluster 任务创建接口返回的轻量 schema。

注意这里不是最终聚类结果，而是“任务已创建 / 已命中缓存”的即时回执。
最终结果仍然通过 `/jobs/{task_id}/result` 拉取。
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ClusterJobCreateResponse(BaseModel):
    """创建任务后返回给前端的最小任务摘要。"""
    task_id: str
    status: str
    progress: float
    message: str
    summary: Optional[dict] = None


class ClusterStageArtifactResponse(BaseModel):
    """staged session 下某个 artifact 的轻量摘要。"""
    artifact_id: str
    stage: str
    status: str
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    last_accessed_at: Optional[float] = None
    expires_at: Optional[float] = None
    dependency_ids: List[str] = Field(default_factory=list)
    summary: Optional[dict] = None


class ClusterStageSessionResponse(BaseModel):
    """staged session 的查询/触发接口统一返回结构。"""
    session_id: str
    status: str
    progress: float
    message: str
    created_at: float
    updated_at: float
    active_stage: Optional[str] = None
    preview: dict
    available_actions: List[str] = Field(default_factory=list)
    prepare: Optional[ClusterStageArtifactResponse] = None
    distances: List[ClusterStageArtifactResponse] = Field(default_factory=list)
    results: List[ClusterStageArtifactResponse] = Field(default_factory=list)
    execution_time_ms: Optional[int] = None
    performance: Optional[dict] = None
