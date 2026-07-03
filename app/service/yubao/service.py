from app.service.yubao.repository import YubaoRepository
from app.service.yubao.schemas import (
    YubaoGrammarItemsResponse,
    YubaoSuggestionResponse,
    YubaoVocabularyItemsResponse,
)


class YubaoService:
    def __init__(self, repository: YubaoRepository | None = None):
        self.repository = repository or YubaoRepository()

    def get_vocabulary_words(self, q: str | None, limit: int, all_items: bool) -> YubaoSuggestionResponse:
        items = self.repository.list_distinct_words(q=q, limit=limit, all_items=all_items)
        total = self.repository.count_distinct_words(q=q)
        return YubaoSuggestionResponse(items=items, total=total)

    def get_grammar_sentences(self, q: str | None, limit: int, all_items: bool) -> YubaoSuggestionResponse:
        items = self.repository.list_distinct_sentences(q=q, limit=limit, all_items=all_items)
        total = self.repository.count_distinct_sentences(q=q)
        return YubaoSuggestionResponse(items=items, total=total)

    def get_vocabulary_items(self, word: str, page: int, page_size: int, sort_by: str | None, sort_desc: bool) -> YubaoVocabularyItemsResponse:
        items, total = self.repository.list_vocabulary_items(
            word=word,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )
        return YubaoVocabularyItemsResponse(items=items, total=total, page=page, page_size=page_size)

    def get_grammar_items(self, sentence: str, page: int, page_size: int, sort_by: str | None, sort_desc: bool) -> YubaoGrammarItemsResponse:
        items, total = self.repository.list_grammar_items(
            sentence=sentence,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )
        return YubaoGrammarItemsResponse(items=items, total=total, page=page, page_size=page_size)
