"""
Cluster response schemas.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ClusterJobCreateResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    message: str
    summary: Optional[dict] = None
