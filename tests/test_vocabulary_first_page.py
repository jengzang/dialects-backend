"""Cold first-page work avoidance without changing counts or cache semantics."""
import asyncio
import sqlite3
import pytest

from app.service.vocabulary import query
from tests.test_vocabulary_query_resources import database


def selects(statements):
    return [sql for sql in statements if sql.startswith(('SELECT', 'WITH'))
            and 'vocabulary_scope_plan' not in sql]


@pytest.mark.parametrize('fields', [['headword'], ['definition', 'headword']])
def test_short_scoped_first_page_skips_count(database, fields):
    _, session, statements = database
    result = query.query_vocabulary_items(session=session, q='日头',
        locations=['贵州'], search_fields=fields)
    assert result.total == 2
    assert [item.id for item in result.items] == [2, 1]
    assert not any(sql.startswith('SELECT COUNT(*)') for sql in statements)


def test_full_page_still_counts_all_matches(database):
    _, session, statements = database
    result = query.query_vocabulary_items(session=session, q='日头', locations=['贵州'],
        search_fields=['headword'], page_size=1)
    assert result.total == 2
    assert [item.id for item in result.items] == [2]
    assert len(selects(statements)) == 2
    assert not selects(statements)[0].startswith('SELECT COUNT(*)')


def test_lazy_count_resolver_reuses_inferred_total_on_every_page(database):
    _, session, statements = database
    totals = {}
    loads = []
    def resolve(sql, values, compute):
        key = sql, tuple(values)
        if key not in totals:
            loads.append(key)
            totals[key] = compute()
        return totals[key]
    params = dict(session=session, q='日头', locations=['贵州'],
                  search_fields=['headword'], _count_resolver=resolve)
    first = query.query_vocabulary_items(**params)
    assert first.total == 2
    assert not any(sql.startswith('SELECT COUNT(*)') for sql in statements)
    statements.clear()
    second = query.query_vocabulary_items(**params, page=2, page_size=1)
    assert second.total == 2 and second.items[0].id == 1
    assert len(selects(statements)) == 1
    assert len(loads) == 1


def test_cached_zero_does_not_load_a_page(database):
    _, session, statements = database
    def resolve(sql, values, compute):
        return 0
    result = query.query_vocabulary_items(session=session, q='无命中', locations=['贵州'],
        search_fields=['headword'], _count_resolver=resolve)
    assert result.total == 0 and result.items == []
    assert selects(statements) == []


@pytest.mark.parametrize('options', [
    {'search_fields': ['detail']},
    {'search_fields': ['headword', 'location']}, {'search_fields': ['all']},
    {'q': '%'}, {'locations': ['%']},
    {'q': '贵州'}, {'province': '贵州'}, {'regions': ['官话/西南']},
    {'standard_words': ['太阳']},
])
def test_unmeasured_shapes_keep_count_first(database, options):
    _, session, statements = database
    params = dict(q='日头', locations=['贵州'], search_fields=['headword'])
    params.update(options)
    query.query_vocabulary_items(session=session, **params)
    assert selects(statements)[0].startswith('SELECT COUNT(*)')


def test_page_and_fallback_count_share_read_snapshot(database):
    conn, session, statements = database
    conn.execute('PRAGMA journal_mode=WAL')
    path = conn.execute('PRAGMA database_list').fetchone()[2]
    with sqlite3.connect(path) as writer:
        wrote = False
        def trace(sql):
            nonlocal wrote
            statements.append(sql)
            if (sql.startswith('SELECT COUNT(*)') or 'vocabulary_scope_count' in sql) and not wrote:
                writer.execute('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) '
                               "VALUES(1,'同名','太阳','日头','z')")
                writer.commit()
                wrote = True
        conn.set_trace_callback(trace)
        result = query.query_vocabulary_items(session=session, q='日头', locations=['贵州'],
            search_fields=['headword'], page_size=1)
    assert wrote
    assert result.total == 2 and result.items[0].id == 2
    assert not conn.in_transaction
    assert conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0] == 5


def test_failed_count_releases_read_savepoint(database):
    conn, session, _ = database
    conn.set_authorizer(lambda action, first, second, *_: sqlite3.SQLITE_DENY
                        if action == sqlite3.SQLITE_FUNCTION and second == 'count'
                        else sqlite3.SQLITE_OK)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            query.query_vocabulary_items(session=session, q='日头', locations=['贵州'],
                search_fields=['headword'], page_size=1)
    finally:
        conn.set_authorizer(None)
    assert not conn.in_transaction
    assert conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0] == 4


def test_read_savepoint_does_not_commit_callers_transaction(database):
    conn, session, _ = database
    conn.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) "
                 "VALUES(1,'同名','太阳','日头','z')")
    result = query.query_vocabulary_items(session=session, q='日头', locations=['贵州'],
        search_fields=['headword'])
    assert result.total == 3
    assert conn.in_transaction
    conn.rollback()
    assert conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0] == 4


def test_cached_search_supplies_lazy_count_loader(database, monkeypatch):
    from app.service.vocabulary import cache as module
    _, session, statements = database
    # Minimal deterministic cache exercises the real cached_search wiring.
    values = {}
    class Cache:
        def call(self, kind, params, load):
            key = kind, repr(params)
            if key not in values:
                values[key] = load()
            return values[key]
        async def acall(self, kind, params, load):
            return await load()
    session.get_bind = lambda: type('Bind', (), {'url': type('URL', (), {'database': 'test.db'})()})()
    monkeypatch.setattr(module, 'get_vocabulary_cache', lambda _: Cache())
    from app.service.vocabulary import resources
    async def direct(path, operation, **kwargs):
        return operation()
    monkeypatch.setattr(resources, 'run_bounded', direct)
    result = asyncio.run(module.cached_search('entries', session, query.query_vocabulary_items,
        q='日头', locations=['贵州'], search_fields=['headword']))
    assert result.total == 2
    assert not any(sql.startswith('SELECT COUNT(*)') for sql in statements)
    statements.clear()
    page = asyncio.run(module.cached_search('entries', session, query.query_vocabulary_items,
        q='日头', locations=['贵州'], search_fields=['headword'], page_size=1, page=2))
    assert page.total == 2 and page.items[0].id == 1
    assert not any(sql.startswith('SELECT COUNT(*)') for sql in statements)
