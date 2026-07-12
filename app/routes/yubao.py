import asyncio

from fastapi import APIRouter, Depends, Query

from app.schemas.yubao import (
    YubaoGrammarItemsResponse,
    YubaoItemsQuery,
    YubaoSuggestionResponse,
    YubaoVocabularyItemsResponse,
)
from app.service.yubao.service import YubaoService

router = APIRouter()
service = YubaoService()


@router.get('/yubao/vocabulary/words', response_model=YubaoSuggestionResponse)
async def get_vocabulary_words(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    all: bool = Query(default=False),
):
    return await asyncio.to_thread(service.get_vocabulary_words, q=q, limit=limit, all_items=all)


@router.get('/yubao/grammar/sentences', response_model=YubaoSuggestionResponse)
async def get_grammar_sentences(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    all: bool = Query(default=False),
):
    return await asyncio.to_thread(service.get_grammar_sentences, q=q, limit=limit, all_items=all)


@router.get('/yubao/vocabulary/items', response_model=YubaoVocabularyItemsResponse)
async def get_vocabulary_items(
    word: str = Query(..., min_length=1),
    query: YubaoItemsQuery = Depends(),
):
    return await asyncio.to_thread(
        service.get_vocabulary_items,
        word=word,
        page=query.page,
        page_size=query.page_size,
        sort_by=query.sort_by,
        sort_desc=query.sort_desc,
    )


@router.get('/yubao/grammar/items', response_model=YubaoGrammarItemsResponse)
async def get_grammar_items(
    sentence: str = Query(..., min_length=1),
    query: YubaoItemsQuery = Depends(),
):
    return await asyncio.to_thread(
        service.get_grammar_items,
        sentence=sentence,
        page=query.page,
        page_size=query.page_size,
        sort_by=query.sort_by,
        sort_desc=query.sort_desc,
    )
