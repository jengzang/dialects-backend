import base64
import binascii
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import ConfigDict, Field, field_validator

from app.schemas.base import ShanghaiBaseModel


SuggestionStatus = Literal["open", "reviewing", "accepted", "rejected", "done"]
SuggestionPriority = Literal["low", "normal", "high"]
MAX_IMAGE_BASE64_BYTES = 1024 * 1024
SUPPORTED_IMAGE_DATA_URL_PREFIXES = (
    "data:image/webp;base64,",
    "data:image/png;base64,",
    "data:image/jpeg;base64,",
)


class SuggestionCreate(ShanghaiBaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)
    category: str = Field("general", min_length=1, max_length=50)
    source_path: Optional[str] = Field(None, max_length=300)
    context: Optional[dict[str, Any]] = None
    contact: Optional[str] = Field(None, max_length=200)
    image_base64: Optional[str] = None

    @field_validator("title", "content", "category", "source_path", "contact")
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空")
        return value

    @field_validator("image_base64")
    @classmethod
    def validate_image_base64(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("截图不能为空")
        if not value.startswith(SUPPORTED_IMAGE_DATA_URL_PREFIXES):
            raise ValueError("截图格式仅支持 webp、png 或 jpeg data URL")
        _, encoded = value.split(",", 1)
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("截图 base64 内容无效") from exc
        if len(image_bytes) > MAX_IMAGE_BASE64_BYTES:
            raise ValueError("截图大小不能超过 1MB")
        return value


class SuggestionCreateResponse(ShanghaiBaseModel):
    success: bool = True
    id: int
    message: str


class SuggestionItem(ShanghaiBaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    title: str
    content: str
    category: str
    source_path: Optional[str] = None
    context: Optional[dict[str, Any]] = None
    contact: Optional[str] = None
    recent_api: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    priority: str
    admin_note: Optional[str] = None
    handled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminSuggestionItem(SuggestionItem):
    image_base64: Optional[str] = None
    submitter_ip: Optional[str] = None
    user_agent: Optional[str] = None


class SuggestionListResponse(ShanghaiBaseModel):
    success: bool = True
    total: int
    page: int
    page_size: int
    items: list[SuggestionItem]


class AdminSuggestionListResponse(ShanghaiBaseModel):
    success: bool = True
    total: int
    page: int
    page_size: int
    items: list[AdminSuggestionItem]


class AdminSuggestionUpdate(ShanghaiBaseModel):
    status: Optional[SuggestionStatus] = None
    priority: Optional[SuggestionPriority] = None
    admin_note: Optional[str] = Field(None, max_length=5000)

    @field_validator("admin_note")
    @classmethod
    def strip_admin_note(cls, value):
        if value is None:
            return value
        value = value.strip()
        return value or None
