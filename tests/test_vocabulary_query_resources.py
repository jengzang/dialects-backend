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
