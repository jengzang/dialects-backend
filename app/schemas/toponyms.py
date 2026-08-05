from pydantic import BaseModel, Field


class ToponymPoint(BaseModel):
    id: str
    longitude: float
    latitude: float


class ToponymPointsResponse(BaseModel):
    items: list[ToponymPoint]
    count: int
    truncated: bool
    next: None = None


class ToponymNamesResponse(BaseModel):
    items: list[str]


class ToponymNameDivisionNode(BaseModel):
    name: str
    level: int
    names: list[str]
    children: list["ToponymNameDivisionNode"]


class ToponymNameTreeResponse(BaseModel):
    items: list[ToponymNameDivisionNode]


class ToponymDetailDivision(BaseModel):
    name: str
    level: int


class ToponymDetail(BaseModel):
    id: str
    name: str
    place_type: str | None
    place_type_code: str | None
    longitude: float | None
    latitude: float | None
    division_path: list[ToponymDetailDivision]


class ToponymDetailsResponse(BaseModel):
    items: list[ToponymDetail]
    count: int


class ToponymDivision(BaseModel):
    code: str
    name: str
    level: int
    single_count: int = Field(alias="single_count")


class ToponymDivisionsResponse(BaseModel):
    items: list[ToponymDivision]
