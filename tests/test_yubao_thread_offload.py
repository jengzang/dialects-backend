import unittest
from unittest.mock import MagicMock, patch

from app.routes import yubao
from app.schemas.yubao import YubaoItemsQuery, YubaoSuggestionResponse, YubaoVocabularyItemsResponse


class YubaoRouteThreadOffloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_vocabulary_words_uses_to_thread(self) -> None:
        fake_service = MagicMock()
        fake_service.get_vocabulary_words.return_value = YubaoSuggestionResponse(items=["春"], total=1)
        offloaded = []

        async def fake_to_thread(func, *args, **kwargs):
            offloaded.append((func, args, kwargs))
            return func(*args, **kwargs)

        with (
            patch.object(yubao, "service", fake_service),
            patch("app.routes.yubao.asyncio.to_thread", side_effect=fake_to_thread),
        ):
            result = await yubao.get_vocabulary_words(q="春", limit=10, all=False)

        self.assertEqual(result.items, ["春"])
        self.assertEqual(offloaded[0][0], fake_service.get_vocabulary_words)
        self.assertEqual(offloaded[0][2], {"q": "春", "limit": 10, "all_items": False})

    async def test_vocabulary_items_uses_to_thread(self) -> None:
        fake_service = MagicMock()
        fake_service.get_vocabulary_items.return_value = YubaoVocabularyItemsResponse(
            items=[], total=0, page=2, page_size=20
        )
        offloaded = []

        async def fake_to_thread(func, *args, **kwargs):
            offloaded.append((func, args, kwargs))
            return func(*args, **kwargs)

        with (
            patch.object(yubao, "service", fake_service),
            patch("app.routes.yubao.asyncio.to_thread", side_effect=fake_to_thread),
        ):
            result = await yubao.get_vocabulary_items(
                word="春",
                query=YubaoItemsQuery(page=2, page_size=20, sort_by="id", sort_desc=True),
            )

        self.assertEqual(result.page, 2)
        self.assertEqual(offloaded[0][0], fake_service.get_vocabulary_items)
        self.assertEqual(
            offloaded[0][2],
            {"word": "春", "page": 2, "page_size": 20, "sort_by": "id", "sort_desc": True},
        )


if __name__ == "__main__":
    unittest.main()
