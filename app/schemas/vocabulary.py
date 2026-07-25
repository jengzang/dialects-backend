from typing import Literal

from pydantic import BaseModel, ConfigDict


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


class VocabularyMapPointResponse(BaseModel):
    location_name: str
    location_label: str
    longitude: float
    latitude: float
    entry_count: int


class VocabularyMapPointsResponse(BaseModel):
    points: list[VocabularyMapPointResponse]
    total_entries: int
    total_points: int
    omitted_without_coordinates: int


class VocabularyLocationResponse(BaseModel):
    user_id: int
    location_name: str
    coordinates: str
    province: str
    city: str
    county: str
    town: str
    administrative_village: str
    natural_village: str
    yindian_region: str
    atlas_region: str
    location_label: str


class VocabularyLocationsResponse(BaseModel):
    locations: list[VocabularyLocationResponse]
    total: int
    page: int
    page_size: int


class VocabularyLocationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coordinates: str | None = None
    province: str | None = None
    city: str | None = None
    county: str | None = None
    town: str | None = None
    administrative_village: str | None = None
    natural_village: str | None = None
    yindian_region: str | None = None
    atlas_region: str | None = None


class VocabularyLogResponse(BaseModel):
    id: int
    operation_id: str
    user_id: int
    permission_level: str
    source: str
    action: str
    table_name: str
    target_scope: str
    affected_rows: int
    status: str
    payload_json: str
    created_at: str


class VocabularyLogsResponse(BaseModel):
    logs: list[VocabularyLogResponse]
    total: int
    page: int
    page_size: int


class VocabularyPermissionUpdateRequest(BaseModel):
    permission_level: Literal["edit", "manage"]


class VocabularyPermissionResponse(BaseModel):
    user_id: int
    permission_level: str
