"""Bounded user-owned mutation protocol; all fields are explicit full replacements."""
import math
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

PositiveID = Annotated[StrictInt, Field(gt=0)]


class EditableFields(BaseModel):
    model_config = ConfigDict(extra='forbid')
    簡稱: str = Field(max_length=200)
    音典分區: str = Field(max_length=200)
    經緯度: str = Field(max_length=100)
    聲韻調: str = Field(max_length=100)
    特徵: str = Field(max_length=200)
    值: str = Field(max_length=4000)
    說明: str = Field(max_length=4000)

    @field_validator('簡稱', '音典分區', '經緯度', '特徵', '值')
    @classmethod
    def required_trimmed(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('字段不能为空')
        return value

    @field_validator('經緯度')
    @classmethod
    def coordinates(cls, value):
        # Frontend formatCoord(lng, lat): six decimal places, longitude first.
        value = value.replace('，', ',')
        parts = value.split(',')
        try:
            if len(parts) != 2:
                raise ValueError
            longitude, latitude = map(float, parts)
            if not (math.isfinite(longitude) and math.isfinite(latitude)
                    and -180 <= longitude <= 180 and -90 <= latitude <= 90):
                raise ValueError
        except ValueError:
            raise ValueError('坐标必须为有效的经度,纬度') from None
        return value


class CustomUpdateItem(EditableFields):
    id: PositiveID
    version: PositiveID


class CustomCreateItem(EditableFields):
    client_row_id: str = Field(min_length=1, max_length=100)


class VersionedDeleteItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: PositiveID
    version: PositiveID


def unique_ids(items):
    ids = [item.id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError('重复记录 ID')


class BatchUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: list[CustomUpdateItem] = Field(min_length=1, max_length=50)

    @model_validator(mode='after')
    def unique(self):
        unique_ids(self.items)
        return self


class BatchDeleteByIdRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ids: list[PositiveID] | None = Field(default=None, min_length=1, max_length=50)
    items: list[VersionedDeleteItem] | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode='after')
    def exclusive_unique(self):
        if (self.ids is None) == (self.items is None):
            raise ValueError('只能提交 ids 或 items 之一')
        ids = self.ids if self.ids is not None else [item.id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError('重复记录 ID')
        return self


class SaveCustomDataRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    creates: list[CustomCreateItem] = Field(default_factory=list, max_length=50)
    updates: list[CustomUpdateItem] = Field(default_factory=list, max_length=50)
    deletes: list[VersionedDeleteItem] = Field(default_factory=list, max_length=50)

    @model_validator(mode='after')
    def bounded_unique(self):
        if not 1 <= len(self.creates) + len(self.updates) + len(self.deletes) <= 50:
            raise ValueError('每次提交必须包含 1 至 50 个变更')
        unique_ids([*self.updates, *self.deletes])
        keys = [row.client_row_id for row in self.creates]
        if len(set(keys)) != len(keys):
            raise ValueError('重复 client_row_id')
        return self
