import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.routes.auth import oauth2_scheme
from app.routes.auth_wechat_mini import router
from app.service.auth.core import service
from app.service.auth.database.models import Base, Session as AuthSession, User


class WechatMiniRouteContractTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()

        self.user = User(
            username="route_wechat_mini_user",
            email="route_wechat_mini@example.com",
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
        app.include_router(router, prefix="/api/auth/wechat/mini")
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

    @patch("app.routes.auth_wechat_mini.auth_routes._issue_session_tokens")
    @patch("app.routes.auth_wechat_mini.service.mark_user_login_success")
    @patch("app.routes.auth_wechat_mini.service.get_identity_by_provider_subject")
    @patch("app.routes.auth_wechat_mini.wechat_mini_service.prepare_wechat_mini_auth")
    def test_wechat_mini_auth_login_exposes_session_id_and_provider_metadata(
        self,
        mock_prepare,
        mock_get_identity,
        mock_mark_login,
        mock_issue_tokens,
    ):
        mock_prepare.return_value = {
            "action": "login",
            "user": self.user,
            "payload": {
                "openid": "mini-openid-1",
                "unionid": "mini-unionid-1",
            },
        }
        mock_get_identity.return_value = None
        mock_mark_login.return_value = None
        mock_issue_tokens.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 1800,
            "session_id": "mini-session-id-1",
        }

        response = self.client.post(
            "/api/auth/wechat/mini/auth",
            json={"code": "mini-code-1"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "login")
        self.assertEqual(body["session_id"], "mini-session-id-1")
        self.assertEqual(body["provider"], "wechat_mini")
        self.assertEqual(body["provider_subject"], "mini-unionid-1")

    @patch("app.routes.auth_wechat_mini.wechat_mini_service.prepare_wechat_mini_auth")
    def test_wechat_mini_auth_client_error_maps_to_400(self, mock_prepare):
        mock_prepare.side_effect = ValueError("WeChat Mini code2session 请求失败")

        response = self.client.post(
            "/api/auth/wechat/mini/auth",
            json={"code": "mini-code-auth-error"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "WeChat Mini code2session 请求失败"})

    @patch("app.routes.auth_wechat_mini.wechat_mini_service.register_user_with_wechat_mini")
    def test_wechat_mini_register_client_error_maps_to_400(self, mock_register):
        mock_register.side_effect = ValueError("WeChat Mini appid/appsecret 未配置")

        response = self.client.post(
            "/api/auth/wechat/mini/register",
            json={"code": "mini-code-register-error", "username": "mini_user", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "WeChat Mini appid/appsecret 未配置"})

    @patch("app.routes.auth_wechat_mini.auth_routes._issue_session_tokens")
    @patch("app.routes.auth_wechat_mini.service.mark_user_login_success")
    @patch("app.routes.auth_wechat_mini.wechat_mini_service.register_user_with_wechat_mini")
    def test_wechat_mini_register_login_exposes_session_id_and_provider_metadata(
        self,
        mock_register,
        mock_mark_login,
        mock_issue_tokens,
    ):
        identity = type("Identity", (), {
            "provider_subject": "mini-unionid-2",
        })()
        mock_register.return_value = (self.user, identity)
        mock_mark_login.return_value = None
        mock_issue_tokens.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 1800,
            "session_id": "mini-session-id-2",
        }

        response = self.client.post(
            "/api/auth/wechat/mini/register",
            json={"code": "mini-code-2", "username": "mini_user", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "login")
        self.assertEqual(body["session_id"], "mini-session-id-2")
        self.assertEqual(body["provider"], "wechat_mini")
        self.assertEqual(body["provider_subject"], "mini-unionid-2")

    @patch("app.routes.auth_wechat_mini.auth_routes._load_active_user_from_token")
    @patch("app.routes.auth_wechat_mini.wechat_mini_service.bind_wechat_mini_identity")
    def test_wechat_mini_bind_uses_bound_contract(self, mock_bind, mock_load_user):
        identity = type("Identity", (), {
            "provider_subject": "mini-unionid-3",
        })()
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_bind.return_value = identity

        response = self.client.post(
            "/api/auth/wechat/mini/bind",
            json={"code": "mini-code-3"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "bound")
        self.assertEqual(body["provider"], "wechat_mini")
        self.assertEqual(body["provider_subject"], "mini-unionid-3")
        mock_bind.assert_called_once()
        self.assertEqual(mock_bind.call_args.kwargs["current_session_public_id"], "fresh-session")

    @patch("app.routes.auth_wechat_mini.auth_routes._load_active_user_from_token")
    @patch("app.routes.auth_wechat_mini.wechat_mini_service.rebind_wechat_mini_identity")
    def test_wechat_mini_rebind_uses_bound_contract(self, mock_rebind, mock_load_user):
        identity = type("Identity", (), {
            "provider_subject": "mini-unionid-4",
        })()
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_rebind.return_value = identity

        response = self.client.post(
            "/api/auth/wechat/mini/rebind",
            json={"code": "mini-code-4"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "bound")
        self.assertEqual(body["provider"], "wechat_mini")
        self.assertEqual(body["provider_subject"], "mini-unionid-4")
        mock_rebind.assert_called_once()
        self.assertEqual(mock_rebind.call_args.kwargs["current_session_public_id"], "fresh-session")

    @patch("app.routes.auth_wechat_mini.wechat_mini_service.register_user_with_wechat_mini")
    def test_wechat_mini_register_conflict_returns_conflict_code_and_suggested_action(self, mock_register):
        mock_register.side_effect = service.AuthConflictError(
            "WeChat Mini account already linked",
            conflict_code=service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED,
        )

        response = self.client.post(
            "/api/auth/wechat/mini/register",
            json={"code": "mini-conflict-register", "username": "mini_user", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {
            "detail": {
                "message": "WeChat Mini account already linked",
                "conflict_code": service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED,
                "suggested_action": service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
            }
        })

    @patch("app.routes.auth_wechat_mini.auth_routes._load_active_user_from_token")
    @patch("app.routes.auth_wechat_mini.wechat_mini_service.bind_wechat_mini_identity")
    def test_wechat_mini_bind_conflict_returns_replace_existing_provider_binding(self, mock_bind, mock_load_user):
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_bind.side_effect = service.AuthConflictError(
            "Current account already linked to another WeChat Mini account",
            conflict_code=service.CONFLICT_CODE_CURRENT_ACCOUNT_PROVIDER_MISMATCH,
            suggested_action=service.SUGGESTED_ACTION_REPLACE_EXISTING_PROVIDER_BINDING,
        )

        response = self.client.post(
            "/api/auth/wechat/mini/bind",
            json={"code": "mini-conflict-bind"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {
            "detail": {
                "message": "Current account already linked to another WeChat Mini account",
                "conflict_code": service.CONFLICT_CODE_CURRENT_ACCOUNT_PROVIDER_MISMATCH,
                "suggested_action": service.SUGGESTED_ACTION_REPLACE_EXISTING_PROVIDER_BINDING,
            }
        })

    @patch("app.routes.auth_wechat_mini.auth_routes._load_active_user_from_token")
    @patch("app.routes.auth_wechat_mini.wechat_mini_service.rebind_wechat_mini_identity")
    def test_wechat_mini_rebind_conflict_returns_provider_already_linked(self, mock_rebind, mock_load_user):
        mock_load_user.return_value = (self.user, {"session_id": "fresh-session"})
        mock_rebind.side_effect = service.AuthConflictError(
            "WeChat Mini account already linked to another account",
            conflict_code=service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED,
        )

        response = self.client.post(
            "/api/auth/wechat/mini/rebind",
            json={"code": "mini-conflict-rebind"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {
            "detail": {
                "message": "WeChat Mini account already linked to another account",
                "conflict_code": service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED,
                "suggested_action": service.SUGGESTED_ACTION_LOGIN_THEN_BIND,
            }
        })


if __name__ == "__main__":
    unittest.main()
