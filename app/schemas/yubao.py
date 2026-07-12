from typing import List, Optional, Union

from pydantic import BaseModel, Field

from app.common.config import YUBAO_MAX_PAGE_SIZE


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
    """分页和排序查询参数，用于 vocabulary/grammar items 接口"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=YUBAO_MAX_PAGE_SIZE)
    sort_by: Optional[str] = None
    sort_desc: bool = False
