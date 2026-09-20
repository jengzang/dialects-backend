from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VocabularyUploadResponse(BaseModel):
    success: bool
    location_id: int
    location_name: str
    permission_level: str
    imported_count: int
    deleted_existing_count: int
    skipped_count: int = Field(description="空行数（标准词、方言词、音标均为空），未导入")
    errors: list[str] = Field(
        description="错误行明细（行号 + 原因），这些行已被跳过、未导入",
    )
    parser_mode: str


class VocabularyUploadPreviewResponse(BaseModel):
    success: bool = Field(description="是否存在可导入的行")
    location_name: str
    permission_level: str
    parsed_count: int = Field(description="可成功解析、将被导入的行数")
    would_delete_existing_count: int
    skipped_count: int = Field(description="空行数（标准词、方言词、音标均为空），未导入")
    errors: list[str] = Field(
        description="错误行明细（行号 + 原因），这些行在导入时会被跳过",
    )
    parser_mode: str


class VocabularyItemResponse(BaseModel):
    id: int
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


class VocabularyStandardWordResponse(BaseModel):
    key: str
    standard_word: str
    variants: list[str]
    entry_count: int
    location_count: int


class VocabularyStandardWordsResponse(BaseModel):
    standard_words: list[VocabularyStandardWordResponse]
    total: int


class VocabularyMapPointResponse(BaseModel):
    location_name: str
    province: str = ""
    city: str = ""
    county: str = ""
    town: str = ""
    administrative_village: str = ""
    natural_village: str = ""
    yindian_region: str = ""
    atlas_region: str = ""
    vocabulary_source: str = ""
    description: str = ""
    other: str = ""
    longitude: float
    latitude: float
    entry_count: int
    t1: str = ""
    t2: str = ""
    t3: str = ""
    t4: str = ""
    t5: str = ""
    t6: str = ""
    t7: str = ""
    t8: str = ""
    t9: str = ""
    t10: str = ""


class VocabularyMapPointsResponse(BaseModel):
    points: list[VocabularyMapPointResponse]
    total_entries: int
    total_points: int
    omitted_without_coordinates: int


class VocabularyMapItemResponse(BaseModel):
    id: int
    standard_word: str
    local_expression: str
    ipa: str
    notes: str
    informations: str


class VocabularyMapItemPointResponse(BaseModel):
    location_name: str
    province: str = ""
    city: str = ""
    county: str = ""
    town: str = ""
    administrative_village: str = ""
    natural_village: str = ""
    yindian_region: str = ""
    atlas_region: str = ""
    longitude: float
    latitude: float
    entry_count: int
    items: list[VocabularyMapItemResponse]


class VocabularyMapItemsResponse(BaseModel):
    points: list[VocabularyMapItemPointResponse]
    total_entries: int
    total_points: int
    omitted_without_coordinates: int


class VocabularyLocationOptionResponse(BaseModel):
    location_name: str
    location_label: str
    province: str = ""
    city: str = ""


class VocabularyLocationOptionsResponse(BaseModel):
    locations: list[VocabularyLocationOptionResponse]
    total: int


class VocabularyLocationResponse(BaseModel):
    user_id: int
    username: str = ""
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
    vocabulary_source: str = ""
    description: str = ""
    other: str = ""
    location_label: str
    t1: str = ""
    t2: str = ""
    t3: str = ""
    t4: str = ""
    t5: str = ""
    t6: str = ""
    t7: str = ""
    t8: str = ""
    t9: str = ""
    t10: str = ""


class VocabularyLocationsResponse(BaseModel):
    locations: list[VocabularyLocationResponse]
    total: int
    page: int
    page_size: int


class VocabularyLocationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_location_name: str | None = None
    coordinates: str | None = None
    province: str | None = None
    city: str | None = None
    county: str | None = None
    town: str | None = None
    administrative_village: str | None = None
    natural_village: str | None = None
    yindian_region: str | None = None
    atlas_region: str | None = None
    vocabulary_source: str | None = None
    description: str | None = None
    other: str | None = None
    t1: str | None = None
    t2: str | None = None
    t3: str | None = None
    t4: str | None = None
    t5: str | None = None
    t6: str | None = None
    t7: str | None = None
    t8: str | None = None
    t9: str | None = None
    t10: str | None = None


class VocabularyLocationTransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_name: str
    user_id: int | None = None
    username: str | None = None
    target_user_id: int | None = None
    target_username: str | None = None


class VocabularyLocationTransferResponse(BaseModel):
    success: bool
    location_name: str
    permission_level: str
    source_user_id: int
    source_username: str = ""
    target_user_id: int
    target_username: str = ""
    transferred_entries_count: int


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
    permission_level: Literal["none", "edit", "manage", "one", "two", "three"]


class VocabularyPermissionResponse(BaseModel):
    user_id: int
    permission_level: str | None


class VocabularyMeResponse(BaseModel):
    user_id: int
    permission_level: str | None
    can_upload: bool
    can_manage_entries: bool
    can_view_logs: bool


class VocabularyPermissionsResponse(BaseModel):
    permissions: list[VocabularyPermissionResponse]
    total: int
    page: int
    page_size: int
