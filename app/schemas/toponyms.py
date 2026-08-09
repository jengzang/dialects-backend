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


class ToponymSearchItem(BaseModel):
    id: str
    name: str
    area_code: str | None = None
    place_type_code: str | None = None


class ToponymSearchResponse(BaseModel):
    items: list[ToponymSearchItem]
    count: int
    truncated: bool
    next: None = None


class ToponymNameDivisionNode(BaseModel):
    name: str
    level: int
    names: list[str]
    children: list["ToponymNameDivisionNode"]


class ToponymNameTreeResponse(BaseModel):
    mode: str = "full"
    items: list[ToponymNameDivisionNode]
    levels: int = 4


class ToponymNameTreeBootstrapChild(BaseModel):
    name: str
    level: int


class ToponymNameTreeBootstrapNode(BaseModel):
    name: str
    level: int
    children: list[ToponymNameTreeBootstrapChild]


class ToponymNameTreeLazyFallbackResponse(BaseModel):
    mode: str
    reason: str
    threshold: int
    filtered_count: int
    levels: int
    lazy_bootstrap: list[ToponymNameTreeBootstrapNode]


class ToponymNameTreeLazyChildrenResponse(BaseModel):
    mode: str
    level: int
    parent_path: list[str]
    children: list[ToponymNameTreeBootstrapChild]
    has_more: bool


class ToponymNameTreeLazyNamesResponse(BaseModel):
    mode: str
    level: int
    parent_path: list[str]
    names: list[str]
    page: int
    page_size: int
    has_more: bool


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
