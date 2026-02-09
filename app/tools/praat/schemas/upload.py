"""
Upload-related Pydantic schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UploadMetadata(BaseModel):
    """Audio file metadata."""
    size_bytes: int
    duration_s: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    format: Optional[str] = None


class UploadResponse(BaseModel):
    """Response for upload creation."""
    upload_id: str
    source_filename: str
    detected_mime: Optional[str] = None
    original_meta: UploadMetadata
    normalized_meta: Optional[UploadMetadata] = None
    warnings: List[str] = Field(default_factory=list)


class UploadInfo(BaseModel):
    """Full upload information."""
    upload_id: str
    filename: str
    mime_type: Optional[str]
    size_bytes: int
    duration_s: Optional[float]
    sample_rate: Optional[int]
    channels: Optional[int]
    created_at: datetime
    warnings: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True
