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
