from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.service.admin.analytics import trends
from app.service.auth.database.models import ApiUsageLog, Base
from app.schemas.admin.analytics import RecentTrendsResponse


NOW = datetime(2026, 1, 31, 0, 30)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(trends, "now_utc_naive", lambda: NOW)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def add_log(db, at, path="/api/phonology", user_id=1, duration=0.5):
    db.add(ApiUsageLog(called_at=at, path=path, user_id=user_id,
                       duration=duration, status_code=200))
    db.flush()


def test_thirty_days_includes_older_logs_and_excludes_login_and_future(db):
    add_log(db, NOW - timedelta(days=20))
    add_log(db, NOW - timedelta(hours=2), duration=1)
    add_log(db, NOW - timedelta(hours=2), user_id=None, duration=3)
    add_log(db, NOW - timedelta(days=40))
    add_log(db, NOW, path="/api/auth/login")
    add_log(db, NOW + timedelta(days=1))
    result = trends.get_recent_trends(db, days=30)
    RecentTrendsResponse.model_validate(result)
    assert result["period"] == "30d"
    assert result["summary"]["total_calls"] == 3
    assert result["summary"]["avg_daily_calls"] == 0.1
    latest = next(row for row in result["trends"] if row["time"] == "2026-01-31")
    assert latest["active_users"] == 1
    assert latest["avg_duration"] == 2


def test_hour_buckets_use_beijing_time_and_fill_empty_intervals(db):
    add_log(db, datetime(2026, 1, 30, 16, 5), user_id=1)
    add_log(db, datetime(2026, 1, 30, 16, 10), user_id=1)
    add_log(db, datetime(2026, 1, 30, 16, 15), user_id=2, path="/api/other")
    result = trends.get_recent_trends(db, granularity="hour", days=1)
    row = next(row for row in result["trends"] if row["time"] == "2026-01-31 00:00")
    assert row["total_calls"] == 3
    assert row["active_users"] == 2
    assert row["top_api"] == "/api/phonology"
    assert len(result["trends"]) == 25
    assert result["trends"][-1]["total_calls"] == 0


def test_empty_response_matches_schema(db):
    result = trends.get_recent_trends(db)
    RecentTrendsResponse.model_validate(result)
    assert result["trends"] == []
    assert result["summary"]["peak_time"] is None
    assert result["summary"]["peak_calls"] == 0


def test_year_of_hourly_data_uses_two_aggregates_with_bounded_output(db):
    add_log(db, NOW - timedelta(days=364))
    statements = []
    def collect_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", collect_statement)
    try:
        result = trends.get_recent_trends(db, granularity="hour", days=365)
    finally:
        event.remove(db.bind, "before_cursor_execute", collect_statement)
    assert len(statements) == 2
    assert all("GROUP BY" in statement for statement in statements)
    assert len(result["trends"]) == 8761
    assert result["summary"]["total_calls"] == 1


@pytest.mark.parametrize("kwargs", [{"days": 0}, {"days": 366}, {"granularity": "week"}])
def test_rejects_invalid_parameters(db, kwargs):
    with pytest.raises(ValueError):
        trends.get_recent_trends(db, **kwargs)
