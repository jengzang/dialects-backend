import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock

import pytest
from app.common import fixed_default_cache as cache
from tests.test_fixed_default_cache import MemoryRedis


@pytest.fixture
def redis(tmp_path, monkeypatch):
    client = MemoryRedis()
    monkeypatch.setattr(cache, 'client_or_default', lambda client_arg=None: client)
    monkeypatch.setenv('FIXED_DEFAULT_LOCK_DIR', str(tmp_path / 'locks'))
    return client


def test_yubao_only_caches_unfiltered_all(tmp_path, monkeypatch, redis):
    from app.routes import yubao
    from app.service.yubao import repository
    path = tmp_path / 'yubao.db'
    with sqlite3.connect(path) as db:
        db.execute('create table vocabulary(word text)')
        db.executemany('insert into vocabulary values (?)', [('春',), ('春',), ('夏',), (' ',), (None,)])
        db.execute('create table grammar(sentence text)')
        db.execute("insert into grammar values ('你好')")
    monkeypatch.setattr(repository, 'YUBAO_DB_PATH', str(path))
    monkeypatch.setitem(yubao.DB_MAPPING, 'yubao', str(path))
    async def run():
        for q in (None, ''):
            result = await yubao.get_vocabulary_words(q=q, limit=50, all=True)
            assert (result.model_dump() if hasattr(result, 'model_dump') else result) == {'items': ['夏', '春'], 'total': 2}
        await yubao.get_grammar_sentences(q=None, limit=50, all=True)
        assert len(redis.values) == 2
        before = dict(redis.values)
        await yubao.get_vocabulary_words(q=' ', limit=50, all=True)
        await yubao.get_vocabulary_words(q=None, limit=1, all=False)
        assert before == redis.values
    asyncio.run(run())


def test_sql_exact_defaults_and_permissions_before_hit(tmp_path, monkeypatch, redis):
    from app.sql import sql_routes as routes
    from app.sql import choose_db
    path = tmp_path / 'counts.db'
    with sqlite3.connect(path) as db:
        db.execute('create table dialects ("存儲標記" integer)')
        db.executemany('insert into dialects values (?)', [(1,), (0,), (1,)])
    for module in (routes, choose_db):
        monkeypatch.setitem(module.DB_MAPPING, 'query', str(path))
        monkeypatch.setitem(module.DB_MAPPING, 'dialects', str(path))
    routes._SCHEMA_CACHE.clear()
    async def run():
        # First pool construction may enable WAL and change the file generation.
        for _ in range(2):
            assert await routes.get_table_count('query', 'dialects', '存儲標記', '1', user=None, auth_db=None) == {'count': 2}
        assert await routes.get_table_count('dialects', 'dialects', user=None, auth_db=None) == {'count': 3}
        assert len(redis.values) == 2
        await routes.get_table_count('query', 'dialects', '存儲標記', '0', user=None, auth_db=None)
        assert len(redis.values) == 2
        monkeypatch.setattr(choose_db, '_check_read_permission', lambda *args: False)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as denied:
            await routes.get_table_count('dialects', 'dialects', user=None, auth_db=None)
        assert denied.value.status_code == 403
    asyncio.run(run())


def test_villages_defaults_only_and_no_connection_on_hit(tmp_path, monkeypatch, redis):
    from app.villagesML import statistics
    from app.villagesML.metadata import stats
    path = tmp_path / 'villages.db'
    with sqlite3.connect(path) as db:
        db.execute('create table demo (n)')
    load_ngrams = Mock(return_value={'ngram_significance': {'total': 3}})
    load_tables = Mock(return_value=[{'table_name': 'demo'}])
    for module in (statistics, stats):
        monkeypatch.setattr(module, 'resolve_db_path', lambda key: str(path))
    monkeypatch.setattr(statistics, '_load_ngram_statistics_sync', load_ngrams)
    monkeypatch.setattr(stats, '_get_table_info_sync', load_tables)
    async def run():
        for _ in range(2):
            assert await statistics.get_ngram_statistics(dbpath='village') == load_ngrams.return_value
            assert await stats.get_table_info(dbpath='village') == load_tables.return_value
        assert load_ngrams.call_count == load_tables.call_count == 1
        await statistics.get_ngram_statistics(dbpath='village_admin')
        await stats.get_table_info(dbpath='village_admin')
        assert load_ngrams.call_count == load_tables.call_count == 2
    asyncio.run(run())


def test_feature_stats_never_uses_result_cache(monkeypatch):
    from app.routes.core import phonology
    payload = SimpleNamespace(locations=['a'], chars=['字'], features=[], filters={})
    load = Mock(return_value={'data': [{'n': 1}]})
    redis_reads = AsyncMock(return_value=None)
    from app.redis_client import redis_client
    monkeypatch.setattr(redis_client, 'get', redis_reads)
    monkeypatch.setattr(phonology, 'get_feature_statistics', load)
    async def run():
        for _ in range(2):
            assert await phonology.feature_stats(payload, dialects_db='test.db') == load.return_value
        assert load.call_count == 2
        assert redis_reads.call_count == 0
    asyncio.run(run())


def test_compare_keeps_only_charlist_cache(monkeypatch):
    from app.routes.core import compare
    from app.service.core import new_pho, status_arrange_pho
    from app.service.geo import getloc_by_name_region
    payload = SimpleNamespace(
        path_strings1=['a'], path_strings2=['b'], column1='聲母', column2='聲母',
        combine_query1=False, combine_query2=False, exclude_columns1=[], exclude_columns2=[],
        chars1=[], chars2=[], table_name='characters', regions=[], locations=['test'],
        region_mode='yindian', features=['聲母'])
    values, reads = {}, []
    async def get(key):
        reads.append(key)
        return values.get(key)
    async def put(key, value, **kwargs):
        values[key] = value
    monkeypatch.setattr(new_pho, 'get_cache', get)
    monkeypatch.setattr(new_pho, 'set_cache', put)
    monkeypatch.setattr(new_pho, 'generate_cache_key', lambda paths, *a, **k: 'charlist:' + paths[0])
    chars = Mock(return_value=[{'chars': ['字']}])
    stats = Mock(return_value={'test': {'聲母': {'total': 1, 'values': []}}})
    locations = Mock(return_value=['test'])
    monkeypatch.setattr(new_pho, 'process_chars_status', chars)
    monkeypatch.setattr(status_arrange_pho, 'query_by_status_stats_only', stats)
    monkeypatch.setattr(getloc_by_name_region, 'query_dialect_abbreviations', locations)
    async def run():
        for _ in range(2):
            result = await compare.compare_zhonggu(payload, dialects_db='test.db', query_db='test.db')
            assert result['status'] == 'success'
        assert all(key.startswith('charlist:') for key in reads)
        assert len(values) == 2
        assert chars.call_count == 2
        assert stats.call_count == 4
        assert locations.call_count == 2
    asyncio.run(run())
