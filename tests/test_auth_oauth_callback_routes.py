import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.routes.auth import router, oauth2_scheme
from app.service.auth.database.models import Base, Session as AuthSession, User


class OAuthCallbackRouteTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()

        self.user = User(
            username="route_oauth_user",
            email="route_oauth@example.com",
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

    @patch("app.routes.auth.service.complete_google_oauth_callback")
    def test_google_callback_login_exposes_session_id(self, mock_complete):
        mock_complete.return_value = {
            "action": "login",
            "message": "Google 登录成功",
            "username": self.user.username,
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 1800,
            "session_id": "session-public-id",
            "email": "route_oauth@example.com",
            "is_verified": True,
            "profile_picture": "https://example.com/google.png",
        }

        response = self.client.post(
            "/api/auth/google/auth/callback",
            json={"state": "abcdefgh", "id_token": "x" * 30},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "login")
        self.assertEqual(body["session_id"], "session-public-id")

    @patch("app.routes.auth.service.complete_google_oauth_callback")
    def test_google_callback_bind_exposes_provider_fields(self, mock_complete):
        mock_complete.return_value = {
            "action": "bound",
            "message": "Google 绑定成功",
            "provider": "google",
            "provider_subject": "google-subject-1",
        }

        response = self.client.post(
            "/api/auth/google/auth/callback",
            json={"state": "abcdefgh", "id_token": "x" * 30},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "bound")
        self.assertEqual(body["provider"], "google")
        self.assertEqual(body["provider_subject"], "google-subject-1")

    @patch("app.routes.auth.service.complete_wechat_oauth_callback")
    def test_wechat_callback_login_exposes_session_id(self, mock_complete):
        mock_complete.return_value = {
            "action": "login",
            "message": "WeChat 登录成功",
            "username": self.user.username,
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 1800,
            "session_id": "wechat-session-public-id",
            "profile_picture": "https://example.com/wechat.png",
            "provider_subject": "wechat-unionid-1",
        }

        response = self.client.post(
            "/api/auth/wechat/auth/callback",
            json={"state": "abcdefgh", "access_token": "token", "openid": "openid-1"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "login")
        self.assertEqual(body["session_id"], "wechat-session-public-id")
        self.assertEqual(body["provider_subject"], "wechat-unionid-1")

    @patch("app.routes.auth.service.complete_wechat_oauth_callback")
    def test_wechat_callback_bind_exposes_provider_fields(self, mock_complete):
        mock_complete.return_value = {
            "action": "bound",
            "message": "WeChat 绑定成功",
            "provider": "wechat",
            "provider_subject": "wechat-unionid-2",
        }

        response = self.client.post(
            "/api/auth/wechat/auth/callback",
            json={"state": "abcdefgh", "access_token": "token", "openid": "openid-2"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "bound")
        self.assertEqual(body["provider"], "wechat")
        self.assertEqual(body["provider_subject"], "wechat-unionid-2")


if __name__ == "__main__":
    unittest.main()
