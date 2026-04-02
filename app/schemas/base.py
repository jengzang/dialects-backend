from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.common.time_utils import to_shanghai_iso


class ShanghaiBaseModel(BaseModel):
    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_datetimes(self, value):
        if isinstance(value, datetime):
            return to_shanghai_iso(value)
        return value
