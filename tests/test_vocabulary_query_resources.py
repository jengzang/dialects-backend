"""Full-result equivalence and query resource regression coverage."""
import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from app.service.vocabulary.models import Base
from app.service.vocabulary.query import (
    query_vocabulary_items, query_vocabulary_map_points,
    query_vocabulary_standard_words,
)
from app.service.vocabulary.script_variants import standard_word_key


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'query.db'
    engine = create_engine(f'sqlite:///{path}')
    Base.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(path)
    conn.executemany('INSERT INTO vocabulary_locations (user_id, location_name, coordinates, province, city, yindian_region) VALUES (?,?,?,?,?,?)', [
        (1, '同名', '106,27', '贵州', '贵阳', '官话/西南'),
        (2, '同名', '107,28', '广东', '广州', '粤语/广府'),
    ])
    conn.executemany('INSERT INTO vocabulary_entries (user_id,location_name,standard_word,local_expression,ipa,notes) VALUES (?,?,?,?,?,?)', [
        (1, '同名', '太阳', '日头', 'a', ''),
        (1, '同名', '太陽', '日頭', 'b', ''),
        (2, '同名', '太阳', '太阳', 'c', '备注'),
        (9, '孤立地点', '月亮', '月光', 'd', ''),
    ])
    conn.commit()
    statements = []
    conn.set_trace_callback(statements.append)
    session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=conn))
    yield conn, session, statements
    conn.close()


def test_count_without_metadata_keeps_orphan_rows_without_join(database):
    _, session, statements = database
    result = query_vocabulary_items(session=session)
    assert result.total == 4
    assert [i.id for i in result.items] == [4, 3, 2, 1]
    counts = [s for s in statements if s.startswith('SELECT COUNT(*)')]
    assert counts and all('JOIN' not in s for s in counts)


@pytest.mark.parametrize('params,expected', [
    ({'province': '广东'}, [3]),
    ({'city': '贵阳'}, [2, 1]),
    ({'q': '广州', 'search_fields': ['location']}, [3]),
    ({'locations': ['广东']}, [3]),
    ({'standard_words': ['太阳']}, [3, 2, 1]),
    ({'q': '不存在'}, []),
])
def test_count_and_items_preserve_all_filter_semantics(database, params, expected):
    _, session, _ = database
    result = query_vocabulary_items(session=session, **params)
    assert result.total == len(expected)
    assert [i.id for i in result.items] == expected


def test_full_word_aggregation_uses_cursor_without_materializing_sql_rows(database):
    conn, _, _ = database
    class Cursor:
        def __init__(self): self.cursor = conn.cursor()
        def execute(self, *args): self.cursor.execute(*args); return self
        def __iter__(self): return iter(self.cursor)
        def fetchall(self): pytest.fail('unbounded SQL intermediate materialized')
    session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=SimpleNamespace(cursor=Cursor)))
    result = query_vocabulary_standard_words(session=session, limit=None)
    assert result.total == len(result.standard_words) == 2
    first = result.standard_words[0]
    assert (first.standard_word, first.entry_count, first.location_count, first.variants) == ('太阳', 3, 1, ['太阳', '太陽'])
    limited = query_vocabulary_standard_words(session=session, limit=1)
    assert limited.standard_words == result.standard_words[:1]
    assert limited.total == result.total


def test_canonical_cache_is_bounded():
    assert standard_word_key.cache_info().maxsize is not None


def test_map_aggregation_preserves_orphans_counts_order_and_filters(database):
    _, session, statements = database
    result = query_vocabulary_map_points(session=session)
    assert result.total_entries == 4
    assert result.omitted_without_coordinates == 1
    assert [(p.longitude, p.entry_count) for p in result.points] == [(106, 2), (107, 1)]
    assert any('FROM (SELECT' in s for s in statements)
    filtered = query_vocabulary_map_points(session=session, locations='广东')
    assert filtered.total_entries == 1
    assert filtered.points[0].longitude == 107


@pytest.mark.parametrize('params,expected', [
    ({}, [4, 3]),
    ({'q': '日', 'search_fields': ['headword']}, [2, 1]),
    ({'standard_words': ['太阳']}, [3, 2]),
    ({'regions': ['官话/西南']}, [2, 1]),
    ({'page': 2}, [2, 1]),
])
def test_entries_page_before_location_join(database, params, expected):
    _, session, statements = database
    result = query_vocabulary_items(session=session, page_size=2, **params)
    assert [item.id for item in result.items] == expected
    selects = [sql for sql in statements if sql.startswith('SELECT')]
    assert selects[0].startswith('SELECT COUNT(*)')
    page_sql = selects[-1]
    assert 'FROM (SELECT' in page_sql
    assert page_sql.index('LIMIT') < page_sql.index('LEFT JOIN vocabulary_locations l')
    if expected[0] == 4:
        assert result.items[0].location_label == '孤立地点'


@pytest.mark.parametrize('params,expected', [
    ({'province': '贵州'}, [2]),
    ({'city': '广州'}, [3]),
])
def test_entries_metadata_filter_stays_before_pagination(database, params, expected):
    _, session, statements = database
    result = query_vocabulary_items(session=session, page_size=1, **params)
    assert [item.id for item in result.items] == expected
    selects = [sql for sql in statements if sql.startswith('SELECT')]
    assert selects[0].startswith('SELECT COUNT(*)')
    page_sql = selects[-1]
    assert page_sql.index('LEFT JOIN vocabulary_locations l') < page_sql.index('LIMIT')


@pytest.mark.parametrize('params,total', [
    ({'q': '不存在'}, 0),
    ({'page': 3, 'page_size': 2}, 4),
    ({'q': '日', 'search_fields': ['headword'], 'page': 2, 'page_size': 2}, 2),
    ({'province': '不存在'}, 0),
])
def test_entries_empty_or_out_of_range_only_counts(database, params, total):
    _, session, statements = database
    result = query_vocabulary_items(session=session, **params)
    assert result.items == []
    assert result.total == total
    assert [sql for sql in statements if sql.startswith('SELECT')] == [
        next(sql for sql in statements if sql.startswith('SELECT COUNT(*)'))
    ]


def test_entries_cached_count_shortcuts_empty_page(database):
    _, session, statements = database
    counts = []
    def cached_count(sql, values):
        counts.append((sql, values))
        return 4
    result = query_vocabulary_items(session=session, page=3, page_size=2,
                                    _count_loader=cached_count)
    assert result.items == [] and result.total == 4
    assert len(counts) == 1
    assert not any(sql.startswith('SELECT') for sql in statements)


@pytest.mark.parametrize('params', [
    {},
    {'q': '不存在'},
    {'page': 3, 'page_size': 2},
    {'province': '贵州', 'page_size': 1},
    {'q': '日头', 'locations': ['贵州'], 'page_size': 1, 'page': 2},
    {'standard_words': ['太阳'], 'page_size': 2, 'page': 2},
])
def test_entries_http_matches_service_contract(database, monkeypatch, params):
    from dataclasses import asdict
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from app.routes import vocabulary
    from app.service.vocabulary import cache

    conn, session, _ = database
    expected = asdict(query_vocabulary_items(session=session, **params))
    path = conn.execute('PRAGMA database_list').fetchone()[2]
    engine = create_engine(f'sqlite:///{path}', connect_args={'check_same_thread': False})
    factory = sessionmaker(bind=engine)
    def get_db():
        with factory() as db:
            yield db
    monkeypatch.setattr(cache, 'get_vocabulary_cache', lambda path: None)
    app = FastAPI()
    app.include_router(vocabulary.router, prefix='/api/vocabulary')
    app.dependency_overrides[vocabulary.get_vocabulary_db] = get_db
    try:
        with TestClient(app) as client:
            response = client.get('/api/vocabulary/search/entries', params=params)
        assert response.status_code == 200
        assert response.json() == expected
    finally:
        engine.dispose()
