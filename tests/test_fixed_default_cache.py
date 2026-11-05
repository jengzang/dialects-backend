import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from app.common import fixed_default_cache as cache


class MemoryRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value


@pytest.fixture
def setup_cache(tmp_path, monkeypatch):
    path = tmp_path / 'test.db'
    with sqlite3.connect(path) as db:
        db.execute('create table items (value text)')
    monkeypatch.setenv('FIXED_DEFAULT_LOCK_DIR', str(tmp_path / 'locks'))
    return str(path), MemoryRedis()


def test_same_version_zero_and_fixed_key_replacement(setup_cache):
    path, client = setup_cache
    loader = Mock(return_value={'count': 0})
    for _ in range(2):
        assert cache.call('sql:dialects_count', path, loader, client=client) == {'count': 0}
    assert loader.call_count == 1
    with sqlite3.connect(path) as db:
        db.execute("insert into items values ('new')")
    cache.call('sql:dialects_count', path, loader, client=client)
    assert loader.call_count == 2
    assert len(client.values) == 1


def test_no_publish_if_version_changes_during_query(setup_cache):
    path, client = setup_cache
    def load():
        with sqlite3.connect(path) as db:
            db.execute("insert into items values ('new')")
        return []
    assert cache.call('yubao:vocabulary_all', path, load, client=client) == []
    assert not client.values


def test_corruption_oversize_redis_failure_missing_db(setup_cache, monkeypatch):
    path, client = setup_cache
    client.values[cache.key('yubao:vocabulary_all')] = '{bad'
    assert cache.call('yubao:vocabulary_all', path, lambda: [], client=client) == []
    assert json.loads(next(iter(client.values.values())))['payload'] == []
    client.values.clear()
    monkeypatch.setattr(cache, 'MAX_PAYLOAD_BYTES', 10)
    assert cache.call('yubao:vocabulary_all', path, lambda: ['x' * 100], client=client) == ['x' * 100]
    assert not client.values
    broken = Mock()
    broken.get.side_effect = ConnectionError()
    assert cache.call('sql:dialects_count', path, lambda: 7, client=broken) == 7
    assert cache.call('sql:dialects_count', path + '.missing', lambda: 8, client=client) == 8
    with pytest.raises(ValueError):
        cache.call('arbitrary-key', path, lambda: 9, client=client)


def test_request_does_not_wait_for_background_lock(setup_cache):
    path, client = setup_cache
    entered, finish = threading.Event(), threading.Event()
    def background():
        with cache.publication_lock() as acquired:
            assert acquired
            entered.set()
            assert finish.wait(3)
    with ThreadPoolExecutor(max_workers=2) as pool:
        bg = pool.submit(background)
        assert entered.wait(2)
        try:
            req = pool.submit(cache.call, 'sql:dialects_count', path, lambda: {'count': 9}, client=client)
            assert req.result(timeout=1) == {'count': 9}
            assert not client.values
        finally:
            finish.set()
        bg.result(timeout=2)


def test_wal_and_file_replacement_change_version(setup_cache):
    path, _ = setup_cache
    before = cache.version(path)
    with sqlite3.connect(path) as db:
        db.execute('pragma journal_mode=wal')
        db.execute("insert into items values ('a')")
        db.commit()
        assert cache.version(path) != before
    before = cache.version(path)
    import os
    os.replace(path, path + '.old')
    with sqlite3.connect(path) as db:
        db.execute('create table replacement (n)')
    assert cache.version(path) != before
