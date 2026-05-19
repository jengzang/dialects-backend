import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.routes.auth import router, oauth2_scheme
from app.service.auth import core as auth_core
from app.service.auth.database.models import Base, Session as AuthSession, User


class OAuthStartRouteTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()

        self.user = User(
            username="route_oauth_start_user",
            email="route_oauth_start@example.com",
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

    @patch("app.routes.auth.service.start_google_oauth")
    def test_google_auth_start_returns_oauth_payload(self, mock_start):
        mock_start.return_value = {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
            "state": "google-state-1",
            "expires_in": 600,
            "intent": auth_core.service.OAUTH_INTENT_LOGIN_OR_REGISTER,
        }

        response = self.client.post(
            "/api/auth/google/auth/start",
            json={
                "intent": auth_core.service.OAUTH_INTENT_LOGIN_OR_REGISTER,
                "redirect_uri": "https://frontend.example/google/callback",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state"], "google-state-1")
        self.assertEqual(body["intent"], auth_core.service.OAUTH_INTENT_LOGIN_OR_REGISTER)
        mock_start.assert_called_once()
        self.assertEqual(mock_start.call_args.kwargs["intent"], auth_core.service.OAUTH_INTENT_LOGIN_OR_REGISTER)
        self.assertEqual(mock_start.call_args.kwargs["redirect_uri"], "https://frontend.example/google/callback")
        self.assertIsNone(mock_start.call_args.kwargs["current_user"])

    def test_google_auth_start_rejects_bind_intent(self):
        response = self.client.post(
            "/api/auth/google/auth/start",
            json={"intent": auth_core.service.OAUTH_INTENT_BIND},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("/google/bind/start", response.json()["detail"])

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.start_google_oauth")
    def test_google_bind_start_forces_bind_intent_and_passes_current_session(self, mock_start, mock_load_user):
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_start.return_value = {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
            "state": "google-bind-state-1",
            "expires_in": 600,
            "intent": auth_core.service.OAUTH_INTENT_BIND,
        }

        response = self.client.post(
            "/api/auth/google/bind/start",
            json={
                "intent": auth_core.service.OAUTH_INTENT_LOGIN_OR_REGISTER,
                "redirect_uri": "https://frontend.example/google/callback",
                "current_session_id": "fresh-session",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["intent"], auth_core.service.OAUTH_INTENT_BIND)
        mock_start.assert_called_once()
        self.assertEqual(mock_start.call_args.kwargs["intent"], auth_core.service.OAUTH_INTENT_BIND)
        self.assertEqual(mock_start.call_args.kwargs["current_user"], self.user)
        self.assertEqual(mock_start.call_args.kwargs["current_session_public_id"], "fresh-session")

    @patch("app.routes.auth.service.start_wechat_oauth")
    def test_wechat_auth_start_returns_oauth_payload(self, mock_start):
        mock_start.return_value = {
            "authorize_url": "https://open.weixin.qq.com/connect/qrconnect?...",
            "state": "wechat-state-1",
            "expires_in": 600,
            "intent": auth_core.service.OAUTH_INTENT_LOGIN_OR_REGISTER,
        }

        response = self.client.post(
            "/api/auth/wechat/auth/start",
            json={
                "intent": auth_core.service.OAUTH_INTENT_LOGIN_OR_REGISTER,
                "redirect_uri": "https://frontend.example/wechat/callback",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state"], "wechat-state-1")
        self.assertEqual(body["intent"], auth_core.service.OAUTH_INTENT_LOGIN_OR_REGISTER)
        mock_start.assert_called_once()
        self.assertEqual(mock_start.call_args.kwargs["intent"], auth_core.service.OAUTH_INTENT_LOGIN_OR_REGISTER)
        self.assertEqual(mock_start.call_args.kwargs["redirect_uri"], "https://frontend.example/wechat/callback")
        self.assertIsNone(mock_start.call_args.kwargs["current_user"])

    def test_wechat_auth_start_rejects_bind_intent(self):
        response = self.client.post(
            "/api/auth/wechat/auth/start",
            json={"intent": auth_core.service.OAUTH_INTENT_BIND},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("/wechat/bind/start", response.json()["detail"])

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.start_wechat_oauth")
    def test_wechat_bind_start_forces_bind_intent_and_passes_current_session(self, mock_start, mock_load_user):
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_start.return_value = {
            "authorize_url": "https://open.weixin.qq.com/connect/qrconnect?...",
            "state": "wechat-bind-state-1",
            "expires_in": 600,
            "intent": auth_core.service.OAUTH_INTENT_BIND,
        }

        response = self.client.post(
            "/api/auth/wechat/bind/start",
            json={
                "intent": auth_core.service.OAUTH_INTENT_LOGIN_OR_REGISTER,
                "redirect_uri": "https://frontend.example/wechat/callback",
                "current_session_id": "fresh-session",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["intent"], auth_core.service.OAUTH_INTENT_BIND)
        mock_start.assert_called_once()
        self.assertEqual(mock_start.call_args.kwargs["intent"], auth_core.service.OAUTH_INTENT_BIND)
        self.assertEqual(mock_start.call_args.kwargs["current_user"], self.user)
        self.assertEqual(mock_start.call_args.kwargs["current_session_public_id"], "fresh-session")


if __name__ == "__main__":
    unittest.main()
