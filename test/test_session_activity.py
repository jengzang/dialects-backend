from __future__ import annotations

import json
from datetime import datetime

from app.schemas.auth.session import SessionActivityResponse
from app.service.admin.sessions import activity as activity_service
from app.service.auth.database.models import RefreshToken, Session


class FakeQuery:
    def __init__(self, items):
        self._items = list(items)

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return list(self._items)


class FakeDB:
    def __init__(self, session: Session | None, tokens: list[RefreshToken]):
        self._session = session
        self._tokens = tokens

    def query(self, model):
        if model is Session:
            return FakeQuery([self._session] if self._session else [])
        if model is RefreshToken:
            return FakeQuery(self._tokens)
        raise AssertionError(f"Unexpected model query: {model}")


def test_get_session_activity_normalizes_mixed_timestamps(monkeypatch):
    monkeypatch.setattr(activity_service, "lookup_ip_location", lambda _ip: "TestLand")

    session = Session(
        id=103,
        session_id="session-103",
        user_id=1,
        username="tester",
        created_at=datetime(2026, 3, 25, 1, 0, 0),
        last_activity_at=datetime(2026, 3, 25, 3, 0, 0),
        revoked=False,
        revoked_at=None,
        revoked_reason=None,
        device_changed=False,
        device_change_count=0,
        is_suspicious=False,
        suspicious_reason=None,
        first_ip="8.8.8.8",
        current_ip="1.1.1.1",
        ip_history=json.dumps([
            {"ip": "8.8.8.8", "timestamp": "2026-03-25T01:00:00"},
            {"ip": "1.1.1.1", "timestamp": "2026-03-25T02:30:00"},
        ]),
    )
    tokens = [
        RefreshToken(
            session_id=103,
            created_at=datetime(2026, 3, 25, 2, 0, 0),
            ip_address="8.8.4.4",
        )
    ]

    result = activity_service.get_session_activity(FakeDB(session, tokens), 103)
    response = SessionActivityResponse(**result)

    assert [event.event_type for event in response.events] == [
        "created",
        "refreshed",
        "ip_changed",
    ]
    assert response.events[0].timestamp.tzinfo is not None
    assert response.events[-1].details.endswith("(TestLand)")
