from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import ConfigDict, Field, field_validator

from app.schemas.base import ShanghaiBaseModel


SuggestionStatus = Literal["open", "reviewing", "accepted", "rejected", "done"]
SuggestionPriority = Literal["low", "normal", "high"]


class SuggestionCreate(ShanghaiBaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)
    category: str = Field("general", min_length=1, max_length=50)
    source_path: Optional[str] = Field(None, max_length=300)
    context: Optional[dict[str, Any]] = None
    contact: Optional[str] = Field(None, max_length=200)

    @field_validator("title", "content", "category", "source_path", "contact")
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空")
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


class SuggestionListResponse(ShanghaiBaseModel):
    success: bool = True
    total: int
    page: int
    page_size: int
    items: list[SuggestionItem]


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
