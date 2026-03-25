from __future__ import annotations

import asyncio
import ast
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.common.auth_config import MAX_SESSIONS_PER_USER
from app.service.admin.sessions import stats as admin_session_stats
from app.service.auth.core import dependencies as auth_dependencies
from app.service.auth.core import utils as auth_utils
from app.service.auth.database.models import Base, RefreshToken, Session, User
from app.service.auth.session import online_time_guard
from app.service.auth.session import service as session_service
from app.service.logging.utils.route_matcher import match_route_config


AUTH_ROUTE_PATH = Path(__file__).resolve().parents[1] / "app" / "routes" / "auth.py"
TRAFFIC_LOGGING_PATH = Path(__file__).resolve().parents[1] / "app" / "service" / "logging" / "middleware" / "traffic_logging.py"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


def create_user(db, username: str = "tester") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="hashed",
        register_ip="1.1.1.1",
        last_login_ip="1.1.1.1",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def build_request(token: str | None) -> Request:
    headers = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode("utf-8")))
    return Request({
        "type": "http",
        "headers": headers,
        "method": "GET",
        "path": "/",
    })


def create_session_record(
    db,
    user: User,
    *,
    public_id: str,
    last_activity_at: datetime | None = None,
    expires_at: datetime | None = None,
    revoked: bool = False,
    current_ip: str = "1.1.1.1",
    device_info: str = "ua",
) -> Session:
    now = datetime.utcnow()
    session = Session(
        session_id=public_id,
        user_id=user.id,
        username=user.username,
        created_at=now - timedelta(hours=1),
        expires_at=expires_at or (now + timedelta(days=30)),
        last_activity_at=last_activity_at or now,
        revoked=revoked,
        first_ip=current_ip,
        current_ip=current_ip,
        device_info=device_info,
        first_device_info=device_info,
        ip_history="[]",
        current_session_started_at=now - timedelta(minutes=5),
        last_seen=now - timedelta(minutes=1),
    )
    db.add(session)
    db.flush()
    return session


def create_refresh_token_record(
    db,
    user: User,
    session: Session,
    *,
    token: str,
    expires_at: datetime,
    revoked: bool = False,
    replaced_by: str | None = None,
    created_at: datetime | None = None,
    ip_address: str = "1.1.1.1",
    device_info: str = "ua",
) -> RefreshToken:
    refresh_token = RefreshToken(
        token=token,
        session_id=session.id,
        user_id=user.id,
        expires_at=expires_at,
        revoked=revoked,
        replaced_by=replaced_by,
        created_at=created_at or datetime.utcnow(),
        ip_address=ip_address,
        device_info=device_info,
    )
    db.add(refresh_token)
    db.flush()
    return refresh_token


def test_refresh_session_extends_session_expiry_sliding_window(db):
    user = create_user(db)
    old_expiry = datetime.utcnow() + timedelta(days=1)
    session = create_session_record(db, user, public_id="session-1", expires_at=old_expiry)
    old_token = create_refresh_token_record(db, user, session, token="old-token", expires_at=old_expiry)
    db.commit()

    access_token, new_refresh_token = session_service.refresh_session(
        db,
        old_token,
        ip_address="1.1.1.1",
        device_info="ua",
    )

    db.refresh(session)
    db.refresh(old_token)
    replacement = db.query(RefreshToken).filter(RefreshToken.token == new_refresh_token).one()

    assert access_token
    assert old_token.revoked is True
    assert session.expires_at > old_expiry
    assert replacement.expires_at == session.expires_at


def test_refresh_session_does_not_reset_online_time_markers(db):
    user = create_user(db)
    old_expiry = datetime.utcnow() + timedelta(days=1)
    session = create_session_record(db, user, public_id="session-online-markers", expires_at=old_expiry)
    old_token = create_refresh_token_record(db, user, session, token="online-markers-token", expires_at=old_expiry)

    old_session_last_seen = datetime.utcnow() - timedelta(minutes=11)
    old_session_started_at = datetime.utcnow() - timedelta(minutes=33)
    old_user_last_seen = datetime.utcnow() - timedelta(minutes=9)
    old_user_started_at = datetime.utcnow() - timedelta(minutes=27)
    session.last_seen = old_session_last_seen
    session.current_session_started_at = old_session_started_at
    user.last_seen = old_user_last_seen
    user.current_session_started_at = old_user_started_at
    db.commit()

    session_service.refresh_session(
        db,
        old_token,
        ip_address="1.1.1.1",
        device_info="ua",
    )

    db.refresh(session)
    db.refresh(user)

    assert session.last_seen == old_session_last_seen
    assert session.current_session_started_at == old_session_started_at
    assert user.last_seen == old_user_last_seen
    assert user.current_session_started_at == old_user_started_at


def test_online_time_queue_avoids_sync_write_fallback():
    source = TRAFFIC_LOGGING_PATH.read_text(encoding="utf-8", errors="ignore")

    assert '_enqueue_with_backpressure(online_time_queue, data, "online_time_queue")' in source
    assert '_write_online_time_batch({' not in source
    assert 'writing directly' not in source


class FakeSyncRedis:
    def __init__(self):
        self.values: dict[str, int] = {}

    def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key, time):
        return True


def test_online_time_guard_rejects_excessive_session_bursts(monkeypatch):
    fake_redis = FakeSyncRedis()
    monkeypatch.setattr(online_time_guard, "sync_redis_client", fake_redis)

    for _ in range(online_time_guard.ONLINE_TIME_SESSION_LIMIT):
        allowed, detail = online_time_guard.check_online_time_report_limits(
            session_id="session-1",
            user_id=1,
            ip_address="1.1.1.1",
        )
        assert allowed is True
        assert detail is None

    allowed, detail = online_time_guard.check_online_time_report_limits(
        session_id="session-1",
        user_id=1,
        ip_address="1.1.1.1",
    )

    assert allowed is False
    assert detail["scope"] == "session"
    assert detail["code"] == "online_time_rate_limited"


def test_online_time_guard_fails_open_on_redis_errors(monkeypatch):
    class BrokenRedis:
        def incr(self, key):
            raise RuntimeError("redis down")

        def expire(self, key, time):
            return True

    monkeypatch.setattr(online_time_guard, "sync_redis_client", BrokenRedis())

    allowed, detail = online_time_guard.check_online_time_report_limits(
        session_id="session-1",
        user_id=1,
        ip_address="1.1.1.1",
    )

    assert allowed is True
    assert detail is None


def test_file_processing_tools_require_login_via_route_config():
    for path in (
        "/api/tools/check/upload",
        "/api/tools/check/execute",
        "/api/tools/merge/execute",
        "/api/tools/jyut2ipa/process",
    ):
        config = match_route_config(path)
        assert config["require_login"] is True
        assert config["rate_limit"] is True


def test_pho_pie_routes_require_login_via_route_config():
    for path in (
        "/api/pho_pie_by_value",
        "/api/pho_pie_by_status",
    ):
        config = match_route_config(path)
        assert config["require_login"] is True
        assert config["rate_limit"] is True


def test_create_session_revokes_orphaned_historical_sessions_without_scheduler(db):
    user = create_user(db)
    orphan = create_session_record(
        db,
        user,
        public_id="orphan-session",
        expires_at=datetime.utcnow() + timedelta(days=10),
    )
    create_refresh_token_record(
        db,
        user,
        orphan,
        token="revoked-token",
        expires_at=orphan.expires_at,
        revoked=True,
    )
    db.commit()

    new_session, _, _ = session_service.create_session(
        db,
        user,
        device_info="ua",
        ip_address="2.2.2.2",
    )

    db.refresh(orphan)
    active_sessions = session_service.get_user_active_sessions(db, user.id)

    assert orphan.revoked is True
    assert orphan.revoked_reason == "token_inactive"
    assert [session.id for session in active_sessions] == [new_session.id]


def test_create_session_enforces_exact_session_limit_without_off_by_one(db):
    user = create_user(db)
    base_time = datetime.utcnow() - timedelta(minutes=30)
    existing_sessions: list[Session] = []

    for index in range(MAX_SESSIONS_PER_USER):
        session = create_session_record(
            db,
            user,
            public_id=f"session-{index}",
            last_activity_at=base_time + timedelta(minutes=index),
        )
        create_refresh_token_record(
            db,
            user,
            session,
            token=f"token-{index}",
            expires_at=session.expires_at,
        )
        existing_sessions.append(session)

    db.commit()

    new_session, _, _ = session_service.create_session(
        db,
        user,
        device_info="ua",
        ip_address="3.3.3.3",
    )

    db.refresh(existing_sessions[0])
    active_sessions = session_service.get_user_active_sessions(db, user.id)

    assert existing_sessions[0].revoked is True
    assert existing_sessions[0].revoked_reason == "max_sessions_exceeded"
    assert len(active_sessions) == MAX_SESSIONS_PER_USER
    assert any(session.id == new_session.id for session in active_sessions)


def test_revoke_session_by_public_id_revokes_session_and_tokens(db):
    user = create_user(db)
    session = create_session_record(db, user, public_id="session-public-id")
    refresh_token = create_refresh_token_record(
        db,
        user,
        session,
        token="logout-token",
        expires_at=session.expires_at,
    )
    db.commit()

    assert session_service.revoke_session_by_public_id(db, "session-public-id", reason="logout") is True

    db.refresh(session)
    db.refresh(refresh_token)
    assert session.revoked is True
    assert session.revoked_reason == "logout"
    assert refresh_token.revoked is True


def test_resolve_refresh_token_for_exchange_reuses_recent_rotation(db):
    user = create_user(db)
    session = create_session_record(db, user, public_id="session-reuse")
    old_token = create_refresh_token_record(
        db,
        user,
        session,
        token="old-refresh",
        expires_at=session.expires_at,
        revoked=True,
        replaced_by="new-refresh",
        created_at=datetime.utcnow() - timedelta(seconds=5),
    )
    replacement = create_refresh_token_record(
        db,
        user,
        session,
        token="new-refresh",
        expires_at=session.expires_at,
        created_at=datetime.utcnow(),
    )
    db.commit()

    resolved, reused = session_service.resolve_refresh_token_for_exchange(
        db,
        "old-refresh",
        ip_address="1.1.1.1",
        device_info="ua",
    )

    assert old_token.token != replacement.token
    assert reused is True
    assert resolved is not None
    assert resolved.token == replacement.token


def test_decode_access_token_falls_back_to_old_keys(monkeypatch):
    payload = {"sub": "tester", "exp": int(time.time()) + 60}
    token = jwt.encode(payload, "old-secret", algorithm="HS256")

    monkeypatch.setattr(auth_utils, "get_secret_key", lambda: "new-secret")
    monkeypatch.setattr(auth_utils, "get_old_secret_keys", lambda: ["old-secret"])

    decoded = auth_utils.decode_access_token(token)

    assert decoded["sub"] == "tester"


def test_get_current_admin_user_rejects_revoked_session(db, monkeypatch):
    user = create_user(db, username="admin-user")
    user.role = "admin"
    session = create_session_record(db, user, public_id="revoked-session", revoked=True)
    db.commit()

    monkeypatch.setattr(
        auth_utils,
        "decode_access_token",
        lambda _: {"sub": user.username, "role": "admin", "session_id": session.session_id},
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(auth_dependencies.get_current_admin_user(build_request("access-token"), db))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Session is no longer active"


def test_admin_session_stats_ignore_sessions_without_active_refresh_tokens(db):
    user = create_user(db)

    active_session = create_session_record(db, user, public_id="active-session")
    create_refresh_token_record(
        db,
        user,
        active_session,
        token="active-refresh",
        expires_at=active_session.expires_at,
    )

    stale_session = create_session_record(
        db,
        user,
        public_id="stale-session",
        last_activity_at=datetime.utcnow(),
    )
    create_refresh_token_record(
        db,
        user,
        stale_session,
        token="stale-refresh",
        expires_at=stale_session.expires_at,
        revoked=True,
    )
    db.commit()

    stats = admin_session_stats.get_session_stats(db)
    online = admin_session_stats.get_online_users(db, threshold_minutes=5)
    history = admin_session_stats.get_user_session_history(db, user.id)

    assert stats["active_sessions"] == 1
    assert online["total_online_sessions"] == 1
    assert online["users"][0]["sessions"][0]["session_id"] == active_session.session_id
    assert history["active_count"] == 1


def test_auth_routes_use_active_session_helper():
    source = AUTH_ROUTE_PATH.read_text(encoding="utf-8", errors="ignore")
    module = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    for function_name in ["me", "logout", "report_online_time", "update_profile", "get_leaderboard"]:
        assert "_load_active_user_from_token" in functions[function_name]
    assert "service.logout_user" not in functions["logout"]
    assert "status_code=503" in functions["report_online_time"]
    assert "check_online_time_report_limits" in functions["report_online_time"]
