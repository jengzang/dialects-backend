import asyncio
from unittest.mock import AsyncMock
import pytest


@pytest.mark.parametrize('all_caches', [False, True])
def test_regular_clear_preserves_fixed_namespace_and_batches(monkeypatch, all_caches):
    from app.service.admin.system import cache as admin
    class Redis:
        delete = AsyncMock(side_effect=lambda *keys: len(keys))
        async def scan_iter(self, match):
            for i in range(205):
                yield f'ordinary:{i}'
            yield 'fixed_default:v1:sql:dialects_count'
            yield b'fixed_default:v1:yubao:grammar_all'
    client = Redis()
    monkeypatch.setattr(admin, 'redis_client', client)
    monkeypatch.setattr(admin, '_RUN_TYPE', 'WEB')
    monkeypatch.setattr(admin, 'clear_dialect_cache', lambda *args: None)
    async def run():
        if all_caches:
            result = await admin.clear_all_cache_logic()
            result = next(item for item in result['results'] if item['type'] == 'redis_cache')
        else:
            result = await admin.clear_redis_cache_logic()
        assert result['deleted_count'] == 205
        assert result['preserved_count'] == 2
        assert all(len(call.args) <= 100 for call in client.delete.call_args_list)
        assert not any(str(key).find('fixed_default:') >= 0 for call in client.delete.call_args_list for key in call.args)
    asyncio.run(run())
