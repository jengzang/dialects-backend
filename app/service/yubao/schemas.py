from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class YubaoSuggestionResponse(BaseModel):
    items: List[str]
    total: int


class YubaoVocabularyItem(BaseModel):
    id: int
    no: Optional[Union[int, float, str]] = None
    province: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    village: Optional[str] = None
    location: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    word: Optional[str] = None
    pronunciation: Optional[str] = None
    note1: Optional[str] = None
    note2: Optional[str] = None
    lang_cat1: Optional[str] = None
    lang_cat2: Optional[str] = None
    lang_cat3: Optional[str] = None


class YubaoGrammarItem(BaseModel):
    id: int
    iid: Optional[int] = None
    city_code: Optional[str] = None
    city_name: Optional[str] = None
    form_a: Optional[str] = None
    form_b: Optional[str] = None
    form_c: Optional[str] = None
    form_d: Optional[str] = None
    form_e: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    phonetic: Optional[str] = None
    sentence: Optional[str] = None
    memo: Optional[str] = None
    lang_cat1: Optional[str] = None
    lang_cat2: Optional[str] = None
    lang_cat3: Optional[str] = None


class YubaoVocabularyItemsResponse(BaseModel):
    items: List[YubaoVocabularyItem]
    total: int
    page: int
    page_size: int


class YubaoGrammarItemsResponse(BaseModel):
    items: List[YubaoGrammarItem]
    total: int
    page: int
    page_size: int


class YubaoItemsQuery(BaseModel):
    page: int = 1
    page_size: int = Field(default=100, le=2000)
    sort_by: Optional[str] = None
    sort_desc: bool = False

    @field_validator('page')
    @classmethod
    def validate_page(cls, v: int) -> int:
        if v < 1:
            raise ValueError('page must be at least 1')
        return v

    @field_validator('page_size')
    @classmethod
    def validate_page_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError('page_size must be at least 1')
        if v > 2000:
            raise ValueError('page_size cannot exceed 2000')
        return v
