from pydantic import BaseModel


class NotesItemResponse(BaseModel):
    id: int
    location_name: str
    character: str
    ipa: str
    notes: str


class NotesSearchResponse(BaseModel):
    items: list[NotesItemResponse]
    total: int
    page: int
    page_size: int
