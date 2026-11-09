import sqlite3
from contextlib import contextmanager

from app.service.logging.stats import hourly_daily_stats as stats


class Pool:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def get_connection(self):
        yield self.conn


def test_stats_exclude_static_without_changing_defaults(monkeypatch):
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE api_usage_daily (date TEXT, path TEXT, call_count INTEGER)')
    conn.executemany('INSERT INTO api_usage_daily VALUES (?, ?, ?)', [
        ('2099-01-01', '/api/search', 10),
        ('2099-01-01', '/assets/main.{hash}.js', 20),
        ('2099-01-01', '/favicon.ico', 5),
    ])
    monkeypatch.setattr(stats, 'get_db_pool', lambda _: Pool(conn))
    assert stats.get_daily_trend(30)['summary']['total_calls'] == 35
    filtered = stats.get_daily_trend(30, exclude_static=True)
    assert filtered['summary']['total_calls'] == 10
    assert filtered['summary']['unique_apis'] == 1
    rank = stats.get_api_ranking(exclude_static=True)
    assert rank['total_calls'] == 10
    assert rank['ranking'][0]['percentage'] == 100
    assert stats.get_api_history('/favicon.ico', exclude_static=True)['summary']['total_calls'] == 0
    assert stats.get_api_history('/api/search', exclude_static=True)['summary']['total_calls'] == 10


def test_static_classification_and_ranking_modes(monkeypatch):
    from app.service.logging.stats.static_paths import is_static_path
    assert is_static_path('/assets/MAIN.{hash}.JS')
    assert is_static_path('/favicon.ico')
    assert not is_static_path('/api/search')
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE api_usage_daily (date TEXT, path TEXT, call_count INTEGER)')
    conn.executemany('INSERT INTO api_usage_daily VALUES (?, ?, ?)', [
        ('2099-01-01', '/api/search', 10),
        ('2099-01-01', '/assets/MAIN.{hash}.JS', 20),
        ('2099-01-02', '/favicon.ico', 5),
    ])
    monkeypatch.setattr(stats, 'get_db_pool', lambda _: Pool(conn))
    assert stats.get_api_ranking(date='2099-01-01', exclude_static=True)['total_calls'] == 10
    assert stats.get_api_ranking(days=30, exclude_static=True)['total_calls'] == 10
    assert stats.get_daily_trend(30, path='/assets/MAIN.{hash}.JS', exclude_static=True)['summary']['total_calls'] == 0


def test_available_apis_filter_is_opt_in(monkeypatch):
    from app.routes.admin.analytics import leaderboard
    monkeypatch.setattr(leaderboard.leaderboard_service, 'get_available_apis', lambda db: ['/api/search', '/favicon.ico'])
    assert leaderboard.get_available_apis(db=None).apis == ['/api/search', '/favicon.ico']
    assert leaderboard.get_available_apis(exclude_static=True, db=None).apis == ['/api/search']


def test_filter_excludes_spa_pages_but_preserves_api_routes(monkeypatch):
    from app.service.logging.stats.static_paths import is_static_path
    pages = ['/', '/menu', '/menu/pho/matrix', '/explore/tools/praat', '/intro', '/villagesML/foo', '/auth', '/admin', '/detail']
    apis = ['/api/search', '/auth/me', '/admin/users/list', '/sql/query', '/logs/visits/today', '/menu-api']
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE api_usage_daily (date TEXT, path TEXT, call_count INTEGER)')
    conn.executemany('INSERT INTO api_usage_daily VALUES (?, ?, 1)', [('2099-01-01', p) for p in pages + apis])
    monkeypatch.setattr(stats, 'get_db_pool', lambda _: Pool(conn))
    assert all(is_static_path(p) for p in pages)
    assert not any(is_static_path(p) for p in apis)
    assert stats.get_daily_trend(30)['summary']['total_calls'] == len(pages + apis)
    assert stats.get_daily_trend(30, exclude_static=True)['summary']['total_calls'] == len(apis)
    assert {x['path'] for x in stats.get_api_ranking(limit=100, exclude_static=True)['ranking']} == set(apis)
    assert stats.get_api_history('/menu', exclude_static=True)['summary']['total_calls'] == 0


def test_excluded_prefixes_apply_consistently_and_literally(monkeypatch):
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE api_usage_daily (date TEXT, path TEXT, call_count INTEGER)')
    paths = ['/admin', '/admin/users', '/administrator', '/logs/test', '/api/auth/me', '/api/authors', '/a_b/item', '/axb/item', '/api/search']
    conn.executemany('INSERT INTO api_usage_daily VALUES (?, ?, 1)', [('2099-01-01', p) for p in paths])
    monkeypatch.setattr(stats, 'get_db_pool', lambda _: Pool(conn))
    prefixes = ['/admin/', '/logs', '/api/auth', '/a_b']
    assert stats.get_daily_trend(30)['summary']['total_calls'] == len(paths)
    assert stats.get_daily_trend(30, exclude_prefixes=prefixes)['summary']['total_calls'] == 4
    ranking = stats.get_api_ranking(exclude_prefixes=prefixes)
    assert ranking['total_calls'] == 4
    assert {item['path'] for item in ranking['ranking']} == {'/administrator', '/api/authors', '/axb/item', '/api/search'}
    assert stats.get_api_history('/admin/users', exclude_prefixes=prefixes)['summary']['total_calls'] == 0
    assert stats.get_api_history('/administrator', exclude_prefixes=prefixes)['summary']['total_calls'] == 1


def test_available_apis_excludes_prefixes(monkeypatch):
    from app.routes.admin.analytics import leaderboard
    monkeypatch.setattr(leaderboard.leaderboard_service, 'get_available_apis', lambda db: ['/admin/a', '/administrator', '/api/auth/me'])
    assert leaderboard.get_available_apis(exclude_prefix=['/admin', '/api/auth'], db=None).apis == ['/administrator']


def test_repeated_query_parameters_and_validation(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routes.logging.hourly_daily import router
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    conn.execute('CREATE TABLE api_usage_daily (date TEXT, path TEXT, call_count INTEGER)')
    conn.executemany('INSERT INTO api_usage_daily VALUES (?, ?, 1)', [('2099-01-01', '/admin/a'), ('2099-01-01', '/logs/a'), ('2099-01-01', '/administrator')])
    monkeypatch.setattr(stats, 'get_db_pool', lambda _: Pool(conn))
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    result = client.get('/ranking', params=[('exclude_prefix', '/admin'), ('exclude_prefix', '/logs')])
    assert result.status_code == 200
    assert result.json()['total_calls'] == 1
    assert client.get('/daily', params={'exclude_prefix': 'invalid'}).status_code == 422
    assert client.get('/ranking', params=[('exclude_prefix', f'/x{i}') for i in range(21)]).status_code == 422


def test_scan_and_file_patterns_are_filtered_consistently(monkeypatch):
    from app.service.logging.stats.static_paths import is_static_path
    unwanted = ['/.env', '/api/.env.production', '/.git/config', '/admin/.git/HEAD', '/wp-admin/js/', '/app/wp-content/a', '/phpMyAdmin/', '/sql/actuator/env', '/cgi-bin/luci', '/backup.tar.gz', '/index.html', '/config.yaml']
    valid = ['/api/search', '/api/auth/me', '/api/environment', '/api/actuators', '/api/git/status']
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE api_usage_daily (date TEXT, path TEXT, call_count INTEGER)')
    conn.executemany('INSERT INTO api_usage_daily VALUES (?, ?, 1)', [('2099-01-01', p) for p in unwanted + valid])
    monkeypatch.setattr(stats, 'get_db_pool', lambda _: Pool(conn))
    assert all(is_static_path(p) for p in unwanted)
    assert not any(is_static_path(p) for p in valid)
    assert stats.get_api_ranking(exclude_static=True)['total_calls'] == len(valid)
    assert stats.get_daily_trend(30, exclude_static=True)['summary']['total_calls'] == len(valid)
    assert stats.get_daily_trend(30, exclude_prefixes=[''])['summary']['total_calls'] == len(unwanted + valid)


def test_empty_prefix_http_is_equivalent_to_omission(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routes.logging.hourly_daily import router
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    conn.execute('CREATE TABLE api_usage_daily (date TEXT, path TEXT, call_count INTEGER)')
    conn.execute("INSERT INTO api_usage_daily VALUES ('2099-01-01', '/admin/users', 5)")
    monkeypatch.setattr(stats, 'get_db_pool', lambda _: Pool(conn))
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get('/ranking?exclude_prefix=').json() == client.get('/ranking').json()


def test_available_apis_validates_before_query(monkeypatch):
    import pytest
    from fastapi import HTTPException
    from app.routes.admin.analytics import leaderboard
    def unexpected_query(db):
        raise AssertionError('database must not be queried for invalid prefixes')
    monkeypatch.setattr(leaderboard.leaderboard_service, 'get_available_apis', unexpected_query)
    with pytest.raises(HTTPException) as exc:
        leaderboard.get_available_apis(exclude_prefix=['bad'], db=None)
    assert exc.value.status_code == 422
