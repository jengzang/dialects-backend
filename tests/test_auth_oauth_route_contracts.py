import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.routes.auth import router, oauth2_scheme
from app.service.auth.database.models import Base, Session as AuthSession, User


class OAuthAuthRouteContractTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()

        self.user = User(
            username="route_oauth_contract_user",
            email="route_oauth_contract@example.com",
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

    @patch("app.routes.auth._issue_session_tokens")
    @patch("app.routes.auth.service.mark_user_login_success")
    @patch("app.routes.auth.service.get_identity_by_provider_subject")
    @patch("app.routes.auth.service.prepare_google_auth")
    def test_google_auth_login_exposes_session_id(self, mock_prepare, mock_get_identity, mock_mark_login, mock_issue_tokens):
        mock_prepare.return_value = {
            "action": "login",
            "user": self.user,
            "payload": {
                "sub": "google-sub-1",
                "email": "route_oauth_contract@example.com",
                "email_verified": True,
                "picture": "https://example.com/google.png",
            },
        }
        mock_get_identity.return_value = None
        mock_mark_login.return_value = None
        mock_issue_tokens.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 1800,
            "session_id": "session-public-id-1",
        }

        response = self.client.post(
            "/api/auth/google/auth",
            json={"id_token": "x" * 30},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "login")
        self.assertEqual(body["session_id"], "session-public-id-1")

    @patch("app.routes.auth._issue_session_tokens")
    @patch("app.routes.auth.service.mark_user_login_success")
    @patch("app.routes.auth.service.register_user_with_google")
    def test_google_register_login_exposes_session_id(self, mock_register, mock_mark_login, mock_issue_tokens):
        identity = type("Identity", (), {
            "email": "route_oauth_contract@example.com",
            "is_verified": True,
            "profile_picture": "https://example.com/google.png",
        })()
        mock_register.return_value = (self.user, identity)
        mock_mark_login.return_value = None
        mock_issue_tokens.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 1800,
            "session_id": "session-public-id-2",
        }

        response = self.client.post(
            "/api/auth/google/register",
            json={"id_token": "x" * 30, "username": "new_google_user", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "login")
        self.assertEqual(body["session_id"], "session-public-id-2")

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.bind_google_identity")
    def test_google_bind_uses_bound_contract(self, mock_bind, mock_load_user):
        identity = type("Identity", (), {
            "email": "route_oauth_contract@example.com",
            "is_verified": True,
            "profile_picture": "https://example.com/google.png",
            "provider_subject": "google-sub-2",
        })()
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_bind.return_value = identity

        response = self.client.post(
            "/api/auth/google/bind",
            json={"id_token": "x" * 30},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "bound")
        self.assertEqual(body["provider"], "google")
        self.assertEqual(body["provider_subject"], "google-sub-2")

    @patch("app.routes.auth._issue_session_tokens")
    @patch("app.routes.auth.service.mark_user_login_success")
    @patch("app.routes.auth.service.get_identity_by_provider_subject")
    @patch("app.routes.auth.service.prepare_wechat_auth")
    def test_wechat_auth_login_exposes_session_id(self, mock_prepare, mock_get_identity, mock_mark_login, mock_issue_tokens):
        mock_prepare.return_value = {
            "action": "login",
            "user": self.user,
            "payload": {
                "openid": "openid-1",
                "unionid": "unionid-1",
                "headimgurl": "https://example.com/wechat.png",
            },
        }
        mock_get_identity.return_value = None
        mock_mark_login.return_value = None
        mock_issue_tokens.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 1800,
            "session_id": "session-public-id-3",
        }

        response = self.client.post(
            "/api/auth/wechat/web/auth",
            json={"access_token": "token", "openid": "openid-1"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "login")
        self.assertEqual(body["session_id"], "session-public-id-3")

    @patch("app.routes.auth._issue_session_tokens")
    @patch("app.routes.auth.service.mark_user_login_success")
    @patch("app.routes.auth.service.register_user_with_wechat")
    def test_wechat_register_login_exposes_session_id(self, mock_register, mock_mark_login, mock_issue_tokens):
        identity = type("Identity", (), {
            "profile_picture": "https://example.com/wechat.png",
            "provider_subject": "unionid-2",
        })()
        mock_register.return_value = (self.user, identity)
        mock_mark_login.return_value = None
        mock_issue_tokens.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 1800,
            "session_id": "session-public-id-4",
        }

        response = self.client.post(
            "/api/auth/wechat/web/register",
            json={"access_token": "token", "openid": "openid-2", "username": "new_wechat_user", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "login")
        self.assertEqual(body["session_id"], "session-public-id-4")

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.bind_wechat_identity")
    def test_wechat_bind_uses_bound_contract(self, mock_bind, mock_load_user):
        identity = type("Identity", (), {
            "profile_picture": "https://example.com/wechat.png",
            "provider_subject": "unionid-3",
        })()
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_bind.return_value = identity

        response = self.client.post(
            "/api/auth/wechat/web/bind",
            json={"access_token": "token", "openid": "openid-3"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "bound")
        self.assertEqual(body["provider"], "wechat")
        self.assertEqual(body["provider_subject"], "unionid-3")


if __name__ == "__main__":
    unittest.main()
