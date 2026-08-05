from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VocabularySqlBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryParams(VocabularySqlBaseModel):
    table_name: str = "vocabulary_entries"
    page: int = 1
    page_size: int = Field(default=20, le=5000)
    sort_by: Optional[str] = None
    sort_desc: bool = False
    filters: dict[str, list[Any]] = Field(default_factory=dict)
    search_text: Optional[str] = None
    search_columns: list[str] = Field(default_factory=list)

    @field_validator("page")
    @classmethod
    def validate_page(cls, value: int) -> int:
        if value < 1:
            raise ValueError("page must be at least 1")
        return value

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        if value < 1:
            raise ValueError("page_size must be at least 1")
        if value > 500:
            raise ValueError("page_size cannot exceed 500")
        return value


class MutationParams(VocabularySqlBaseModel):
    table_name: str = "vocabulary_entries"
    action: Literal["create", "update", "delete"]
    pk_column: str = "id"
    pk_value: Any = None
    data: dict[str, Any] = Field(default_factory=dict)


class BatchMutationParams(VocabularySqlBaseModel):
    table_name: str = "vocabulary_entries"
    action: Literal["batch_create", "batch_update", "batch_delete"]
    pk_column: str = "id"
    create_data: list[dict[str, Any]] = Field(default_factory=list)
    update_data: list[dict[str, Any]] = Field(default_factory=list)
    delete_ids: list[Any] = Field(default_factory=list)


class DistinctQueryRequest(VocabularySqlBaseModel):
    table_name: str = "vocabulary_entries"
    target_column: str
    current_filters: dict[str, list[Any]] = Field(default_factory=dict)
    search_text: Optional[str] = ""
    search_columns: list[str] = Field(default_factory=list)


class BatchReplacePreviewParams(VocabularySqlBaseModel):
    table_name: str = "vocabulary_entries"
    columns: list[str]
    find_text: str = ""
    match_mode: Literal["exact", "contains"] = "contains"
    is_empty_search: bool = False
    filters: dict[str, list[Any]] = Field(default_factory=dict)
    search_text: Optional[str] = ""
    search_columns: list[str] = Field(default_factory=list)


class BatchReplaceExecuteParams(BatchReplacePreviewParams):
    replace_text: str = ""
