from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.admin.sessions.stats import get_session_stats
from app.service.auth.database.models import Base, RefreshToken, Session, User


def test_session_stats_separates_expired_revoked_and_online_sessions():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    now = datetime.utcnow()
    user = User(
        username="tester",
        email="tester@example.com",
        hashed_password="hash",
    )
    db.add(user)
    db.flush()

    valid_online = Session(
        session_id="valid-online",
        user_id=user.id,
        username=user.username,
        created_at=now - timedelta(hours=2),
        expires_at=now + timedelta(days=1),
        last_activity_at=now - timedelta(minutes=2),
        revoked=False,
        first_ip="127.0.0.1",
        current_ip="127.0.0.1",
        total_online_seconds=3600,
    )
    valid_idle = Session(
        session_id="valid-idle",
        user_id=user.id,
        username=user.username,
        created_at=now - timedelta(hours=3),
        expires_at=now + timedelta(days=1),
        last_activity_at=now - timedelta(minutes=20),
        revoked=False,
        first_ip="127.0.0.1",
        current_ip="127.0.0.1",
        total_online_seconds=7200,
    )
    valid_inactive = Session(
        session_id="valid-inactive",
        user_id=user.id,
        username=user.username,
        created_at=now - timedelta(hours=4),
        expires_at=now + timedelta(days=1),
        last_activity_at=now - timedelta(hours=1),
        revoked=False,
        first_ip="127.0.0.1",
        current_ip="127.0.0.1",
        total_online_seconds=900,
    )
    expired_revoked = Session(
        session_id="expired-revoked",
        user_id=user.id,
        username=user.username,
        created_at=now - timedelta(days=40),
        expires_at=now - timedelta(days=1),
        last_activity_at=now - timedelta(days=2),
        revoked=True,
        revoked_at=now - timedelta(hours=12),
        revoked_reason="expired",
        is_suspicious=True,
        first_ip="127.0.0.1",
        current_ip="127.0.0.1",
        total_online_seconds=1800,
    )
    expired_unrevoked = Session(
        session_id="expired-unrevoked",
        user_id=user.id,
        username=user.username,
        created_at=now - timedelta(days=35),
        expires_at=now - timedelta(hours=1),
        last_activity_at=now - timedelta(hours=2),
        revoked=False,
        first_ip="127.0.0.1",
        current_ip="127.0.0.1",
        total_online_seconds=0,
    )
    db.add_all([valid_online, valid_idle, valid_inactive, expired_revoked, expired_unrevoked])
    db.flush()

    db.add_all(
        [
            RefreshToken(
                token="valid-online-token",
                user_id=user.id,
                session_id=valid_online.id,
                expires_at=now + timedelta(days=1),
                revoked=False,
            ),
            RefreshToken(
                token="valid-idle-token",
                user_id=user.id,
                session_id=valid_idle.id,
                expires_at=now + timedelta(days=1),
                revoked=False,
            ),
            RefreshToken(
                token="valid-inactive-token",
                user_id=user.id,
                session_id=valid_inactive.id,
                expires_at=now + timedelta(days=1),
                revoked=False,
            ),
        ]
    )
    db.commit()

    stats = get_session_stats(db)

    assert stats["total_sessions"] == 5
    assert "active_sessions" not in stats
    assert stats["valid_sessions"] == 3
    assert stats["online_sessions_30m"] == 2
    assert stats["online_users_30m"] == 1
    assert stats["expired_sessions"] == 2
    assert stats["expired_revoked_sessions"] == 1
    assert stats["expired_unrevoked_sessions"] == 1
    assert stats["suspicious_sessions"] == 1
    assert stats["revoked_suspicious_sessions"] == 1
    assert stats["active_suspicious_sessions"] == 0
    assert "avg_session_duration_hours" not in stats
