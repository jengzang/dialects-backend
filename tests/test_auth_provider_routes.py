import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.routes import auth as auth_routes
from app.service.auth.database.connection import get_db
from app.service.auth.database.models import Base


class AuthProviderRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        self.app = FastAPI()
        self.app.include_router(auth_routes.router, prefix="/api/auth")

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.list_auth_providers")
    def test_get_providers_returns_replacement_actions(self, mock_list_auth_providers, mock_load_active_user_from_token):
        mock_load_active_user_from_token.return_value = (type("UserStub", (), {"id": 1, "username": "tester"})(), {"session_id": "sess_1"})
        mock_list_auth_providers.return_value = [
            {
                "provider": "google",
                "email": "tester@gmail.com",
                "display_name": "Tester",
                "is_verified": True,
                "is_primary": False,
                "linked_at": None,
                "last_login_at": None,
                "profile_picture": None,
                "can_unbind": False,
                "can_replace": True,
                "replacement_action": "bind_google",
            },
            {
                "provider": "wechat_mini",
                "email": None,
                "display_name": "Mini Tester",
                "is_verified": True,
                "is_primary": False,
                "linked_at": None,
                "last_login_at": None,
                "profile_picture": None,
                "can_unbind": False,
                "can_replace": True,
                "replacement_action": "bind_wechat_mini",
            },
            {
                "provider": "email",
                "email": "tester@example.com",
                "display_name": None,
                "is_verified": True,
                "is_primary": True,
                "linked_at": None,
                "last_login_at": None,
                "profile_picture": None,
                "can_unbind": False,
                "can_replace": True,
                "replacement_action": "change_email",
            },
        ]

        response = self.client.get("/api/auth/providers", headers={"Authorization": "Bearer fake-token"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[0]["provider"], "google")
        self.assertTrue(body[0]["can_replace"])
        self.assertEqual(body[0]["replacement_action"], "bind_google")
        self.assertEqual(body[1]["provider"], "wechat_mini")
        self.assertEqual(body[1]["replacement_action"], "bind_wechat_mini")
        self.assertTrue(body[1]["can_replace"])
        self.assertEqual(body[2]["replacement_action"], "change_email")

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.unbind_auth_provider")
    @patch("app.routes.auth.service.list_auth_providers")
    def test_delete_provider_returns_legacy_replace_guidance(self, mock_list_auth_providers, mock_unbind_auth_provider, mock_load_active_user_from_token):
        user = type("UserStub", (), {"id": 1, "username": "tester"})()
        mock_load_active_user_from_token.return_value = (user, {"session_id": "sess_1"})
        mock_list_auth_providers.return_value = [
            {
                "provider": "wechat",
                "email": None,
                "display_name": "Tester WX",
                "is_verified": True,
                "is_primary": False,
                "linked_at": None,
                "last_login_at": None,
                "profile_picture": None,
                "can_unbind": False,
                "can_replace": True,
                "replacement_action": "bind_wechat",
            }
        ]

        response = self.client.delete("/api/auth/providers/wechat", headers={"Authorization": "Bearer fake-token"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["message"], "v1 仅支持换绑，不支持解绑")
        self.assertEqual(body["providers"][0]["provider"], "wechat")
        self.assertEqual(body["providers"][0]["replacement_action"], "bind_wechat")
        mock_unbind_auth_provider.assert_called_once_with(unittest.mock.ANY, user, "wechat")
        mock_list_auth_providers.assert_called_once_with(unittest.mock.ANY, user)

    @patch("app.routes.auth._load_active_user_from_token")
    @patch("app.routes.auth.service.list_auth_providers")
    def test_me_returns_auth_providers_with_wechat_mini_replacement_action(self, mock_list_auth_providers, mock_load_active_user_from_token):
        user = type(
            "UserStub",
            (),
            {
                "id": 1,
                "username": "tester",
                "email": "tester@example.com",
                "status": "active",
                "role": "user",
                "is_verified": True,
                "avatar_url": None,
                "bio": None,
                "phone": None,
                "created_at": None,
                "updated_at": None,
                "total_online_seconds": 0,
                "usage_summary": [],
            },
        )()
        mock_load_active_user_from_token.return_value = (user, {"session_id": "sess_1"})
        mock_list_auth_providers.return_value = [
            {
                "provider": "wechat_mini",
                "email": None,
                "display_name": "Mini Tester",
                "is_verified": True,
                "is_primary": False,
                "linked_at": None,
                "last_login_at": None,
                "profile_picture": None,
                "can_unbind": False,
                "can_replace": True,
                "replacement_action": "bind_wechat_mini",
            },
            {
                "provider": "email",
                "email": "tester@example.com",
                "display_name": "tester@example.com",
                "is_verified": True,
                "is_primary": True,
                "linked_at": None,
                "last_login_at": None,
                "profile_picture": None,
                "can_unbind": False,
                "can_replace": True,
                "replacement_action": "change_email",
            },
        ]

        response = self.client.get("/api/auth/me", headers={"Authorization": "Bearer fake-token"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        providers = {item["provider"]: item for item in body["auth_providers"]}
        self.assertEqual(providers["wechat_mini"]["replacement_action"], "bind_wechat_mini")
        self.assertTrue(providers["wechat_mini"]["can_replace"])
        self.assertEqual(providers["email"]["replacement_action"], "change_email")


if __name__ == "__main__":
    unittest.main()
