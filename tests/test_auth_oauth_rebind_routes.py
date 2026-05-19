import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.routes.auth import router, oauth2_scheme
from app.service.auth.database.models import Base, Session as AuthSession, User


class OAuthRebindRouteTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()

        self.user = User(
            username="route_oauth_rebind_user",
            email="route_oauth_rebind@example.com",
            hashed_password="hashed",
            role="user",
            status="active",
            is_verified=True,
            failed_attempts=0,
            total_online_seconds=0,
        )
        self.db.add(self.user)
        self.db.flush()
        self.db.add(AuthSession(
            session_id="fresh-session",
            user_id=self.user.id,
            username=self.user.username,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=7),
            last_activity_at=datetime.now(UTC).replace(tzinfo=None),
            first_ip="127.0.0.1",
            current_ip="127.0.0.1",
            revoked=False,
        ))
        self.db.commit()
        self.db.refresh(self.user)

        app = FastAPI()
        app.include_router(router, prefix="/api/auth")
        app.dependency_overrides[oauth2_scheme] = lambda: "fake-token"
        from app.service.auth.database.connection import get_db

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.rebind_google_identity")
    def test_google_rebind_returns_bound_contract(self, mock_rebind, mock_load_user):
        identity = type("Identity", (), {
            "email": "route_oauth_rebind@example.com",
            "is_verified": True,
            "profile_picture": "https://example.com/google.png",
            "provider_subject": "google-sub-rebound",
        })()
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_rebind.return_value = identity

        response = self.client.post(
            "/api/auth/google/rebind",
            json={"id_token": "x" * 30},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "bound")
        self.assertEqual(body["provider"], "google")
        self.assertEqual(body["provider_subject"], "google-sub-rebound")
        mock_rebind.assert_called_once()
        self.assertEqual(mock_rebind.call_args.kwargs["current_session_public_id"], "fresh-session")

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.rebind_wechat_identity")
    def test_wechat_rebind_returns_bound_contract(self, mock_rebind, mock_load_user):
        identity = type("Identity", (), {
            "profile_picture": "https://example.com/wechat.png",
            "provider_subject": "unionid-rebound",
        })()
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_rebind.return_value = identity

        response = self.client.post(
            "/api/auth/wechat/rebind",
            json={"access_token": "token", "openid": "openid-rebound"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "bound")
        self.assertEqual(body["provider"], "wechat")
        self.assertEqual(body["provider_subject"], "unionid-rebound")
        mock_rebind.assert_called_once()
        self.assertEqual(mock_rebind.call_args.kwargs["current_session_public_id"], "fresh-session")


if __name__ == "__main__":
    unittest.main()
