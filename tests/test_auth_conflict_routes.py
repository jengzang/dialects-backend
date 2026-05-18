import unittest
from unittest.mock import patch
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.routes.auth import router, oauth2_scheme
from app.service.auth.core import service
from app.service.auth.database.models import Base, Session as AuthSession, User


class AuthConflictRouteTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()

        self.user = User(
            username="route_tester",
            email="route@example.com",
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

    @patch("app.routes.auth.service.prepare_google_auth")
    def test_google_auth_conflict_returns_409_with_structured_detail(self, mock_prepare_google_auth):
        mock_prepare_google_auth.return_value = {
            "action": "conflict",
            "conflict_code": service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS,
            "suggested_action": service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
            "payload": {
                "sub": "google-sub-1",
                "email": "taken@example.com",
                "email_verified": True,
                "picture": "https://example.com/google.png",
            },
        }

        response = self.client.post("/api/auth/google/auth", json={"id_token": "x" * 30})
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["detail"]["message"], "该 Google 邮箱已存在，请先用原账号登录后再绑定 Google")
        self.assertEqual(body["detail"]["conflict_code"], service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS)
        self.assertEqual(body["detail"]["suggested_action"], service.SUGGESTED_ACTION_LOGIN_THEN_BIND)

    @patch("app.routes.auth.service.prepare_wechat_auth")
    def test_wechat_auth_conflict_returns_409_with_structured_detail(self, mock_prepare_wechat_auth):
        mock_prepare_wechat_auth.return_value = {
            "action": "conflict",
            "conflict_code": service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS,
            "suggested_action": service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
            "payload": {
                "openid": "openid-1",
                "unionid": "unionid-1",
                "email": "taken@example.com",
                "headimgurl": "https://example.com/wechat.png",
            },
        }

        response = self.client.post(
            "/api/auth/wechat/auth",
            json={"access_token": "token", "openid": "openid-1"},
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["detail"]["message"], "该微信邮箱已存在，请先用原账号登录后再绑定微信")
        self.assertEqual(body["detail"]["conflict_code"], service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS)
        self.assertEqual(body["detail"]["suggested_action"], service.SUGGESTED_ACTION_LOGIN_THEN_BIND)

    @patch("app.routes.auth.service.register_user_with_google")
    def test_google_register_conflict_returns_409_with_detail_object(self, mock_register):
        mock_register.side_effect = service.AuthConflictError(
            "Email already exists, please login and bind Google first",
            conflict_code=service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS,
            suggested_action=service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
        )

        response = self.client.post(
            "/api/auth/google/register",
            json={"id_token": "x" * 30, "username": "new_user", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["detail"]["message"], "Email already exists, please login and bind Google first")
        self.assertEqual(body["detail"]["conflict_code"], service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS)
        self.assertEqual(body["detail"]["suggested_action"], service.SUGGESTED_ACTION_LOGIN_THEN_BIND)

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.bind_google_identity")
    def test_google_bind_provider_conflict_returns_409_with_detail_object(self, mock_bind, mock_load_user):
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_bind.side_effect = service.AuthConflictError(
            "Google account already linked to another account",
            conflict_code=service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED,
            suggested_action=service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
        )

        response = self.client.post("/api/auth/google/bind", json={"id_token": "x" * 30})
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["detail"]["message"], "Google account already linked to another account")
        self.assertEqual(body["detail"]["conflict_code"], service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED)
        self.assertEqual(body["detail"]["suggested_action"], service.SUGGESTED_ACTION_LOGIN_THEN_BIND)

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.bind_google_identity")
    def test_google_bind_current_account_mismatch_returns_replace_action(self, mock_bind, mock_load_user):
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_bind.side_effect = service.AuthConflictError(
            "Current account already linked to another Google account",
            conflict_code=service.CONFLICT_CODE_CURRENT_ACCOUNT_PROVIDER_MISMATCH,
            suggested_action=service.SUGGESTED_ACTION_REPLACE_EXISTING_PROVIDER_BINDING,
        )

        response = self.client.post("/api/auth/google/bind", json={"id_token": "x" * 30})
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["detail"]["message"], "Current account already linked to another Google account")
        self.assertEqual(body["detail"]["conflict_code"], service.CONFLICT_CODE_CURRENT_ACCOUNT_PROVIDER_MISMATCH)
        self.assertEqual(body["detail"]["suggested_action"], service.SUGGESTED_ACTION_REPLACE_EXISTING_PROVIDER_BINDING)

    @patch("app.routes.auth.service.register_user_with_wechat")
    def test_wechat_register_conflict_returns_409_with_detail_object(self, mock_register):
        mock_register.side_effect = service.AuthConflictError(
            "Email already exists, please login and bind WeChat first",
            conflict_code=service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS,
            suggested_action=service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
        )

        response = self.client.post(
            "/api/auth/wechat/register",
            json={"access_token": "token", "openid": "openid-1", "username": "new_user", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["detail"]["message"], "Email already exists, please login and bind WeChat first")
        self.assertEqual(body["detail"]["conflict_code"], service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS)
        self.assertEqual(body["detail"]["suggested_action"], service.SUGGESTED_ACTION_LOGIN_THEN_BIND)

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.bind_wechat_identity")
    def test_wechat_bind_provider_conflict_returns_409_with_detail_object(self, mock_bind, mock_load_user):
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_bind.side_effect = service.AuthConflictError(
            "WeChat account already linked to another account",
            conflict_code=service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED,
            suggested_action=service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
        )

        response = self.client.post(
            "/api/auth/wechat/bind",
            json={"access_token": "token", "openid": "openid-1"},
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["detail"]["message"], "WeChat account already linked to another account")
        self.assertEqual(body["detail"]["conflict_code"], service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED)
        self.assertEqual(body["detail"]["suggested_action"], service.SUGGESTED_ACTION_LOGIN_THEN_BIND)

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.bind_wechat_identity")
    def test_wechat_bind_current_account_mismatch_returns_replace_action(self, mock_bind, mock_load_user):
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_bind.side_effect = service.AuthConflictError(
            "Current account already linked to another WeChat account",
            conflict_code=service.CONFLICT_CODE_CURRENT_ACCOUNT_PROVIDER_MISMATCH,
            suggested_action=service.SUGGESTED_ACTION_REPLACE_EXISTING_PROVIDER_BINDING,
        )

        response = self.client.post(
            "/api/auth/wechat/bind",
            json={"access_token": "token", "openid": "openid-1"},
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["detail"]["message"], "Current account already linked to another WeChat account")
        self.assertEqual(body["detail"]["conflict_code"], service.CONFLICT_CODE_CURRENT_ACCOUNT_PROVIDER_MISMATCH)
        self.assertEqual(body["detail"]["suggested_action"], service.SUGGESTED_ACTION_REPLACE_EXISTING_PROVIDER_BINDING)


if __name__ == "__main__":
    unittest.main()
