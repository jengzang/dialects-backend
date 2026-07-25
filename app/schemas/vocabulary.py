from typing import Literal

from pydantic import BaseModel


class VocabularyUploadResponse(BaseModel):
    success: bool
    location_id: int
    location_name: str
    permission_level: str
    imported_count: int
    deleted_existing_count: int
    skipped_count: int
    errors: list[str]
    parser_mode: str


class VocabularyItemResponse(BaseModel):
    standard_word: str
    local_expression: str
    ipa: str
    notes: str
    informations: str
    location_name: str
    location_label: str


class VocabularyItemsResponse(BaseModel):
    items: list[VocabularyItemResponse]
    total: int
    page: int
    page_size: int


class VocabularyPermissionUpdateRequest(BaseModel):
    permission_level: Literal["edit", "manage"]


class VocabularyPermissionResponse(BaseModel):
    user_id: int
    permission_level: str
