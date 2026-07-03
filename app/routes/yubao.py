from fastapi import APIRouter, Query

from app.service.yubao.schemas import (
    YubaoGrammarItemsResponse,
    YubaoSuggestionResponse,
    YubaoVocabularyItemsResponse,
)
from app.service.yubao.service import YubaoService

router = APIRouter()
service = YubaoService()


@router.get('/yubao/vocabulary/words', response_model=YubaoSuggestionResponse)
def get_vocabulary_words(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    all: bool = Query(default=False),
):
    return service.get_vocabulary_words(q=q, limit=limit, all_items=all)


@router.get('/yubao/grammar/sentences', response_model=YubaoSuggestionResponse)
def get_grammar_sentences(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    all: bool = Query(default=False),
):
    return service.get_grammar_sentences(q=q, limit=limit, all_items=all)


@router.get('/yubao/vocabulary/items', response_model=YubaoVocabularyItemsResponse)
def get_vocabulary_items(
    word: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=2000),
    sort_by: str | None = Query(default=None),
    sort_desc: bool = Query(default=False),
):
    return service.get_vocabulary_items(
        word=word,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )


@router.get('/yubao/grammar/items', response_model=YubaoGrammarItemsResponse)
def get_grammar_items(
    sentence: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=2000),
    sort_by: str | None = Query(default=None),
    sort_desc: bool = Query(default=False),
):
    return service.get_grammar_items(
        sentence=sentence,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )
