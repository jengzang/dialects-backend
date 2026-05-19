import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.routes.auth import router
from app.service.auth.database.models import Base
from app.service.auth.database.connection import get_db


class AuthEmailRouteTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        app = FastAPI()
        app.include_router(router, prefix="/api/auth")

        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    @patch("app.routes.auth.service.start_email_registration")
    def test_register_email_starts_pending_verification(self, mock_start_email_registration):
        mock_start_email_registration.return_value = "opaque-token"

        response = self.client.post(
            "/api/auth/register-email",
            json={"email": "new@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["message"], "验证邮件已发送，请查收邮箱完成注册确认")
        mock_start_email_registration.assert_called_once()

    @patch("app.routes.auth.service.verify_email_registration_token")
    def test_verify_email_registration_returns_ready_payload(self, mock_verify_email_registration_token):
        mock_verify_email_registration_token.return_value = {
            "email": "verified@example.com",
            "ready_to_complete": True,
        }

        response = self.client.get("/api/auth/verify-email-registration?token=test-token")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"email": "verified@example.com", "ready_to_complete": True},
        )
        mock_verify_email_registration_token.assert_called_once_with(unittest.mock.ANY, "test-token")

    @patch("app.routes.auth.service.complete_email_registration")
    def test_complete_email_registration_returns_user_profile(self, mock_complete_email_registration):
        user = type(
            "UserStub",
            (),
            {
                "id": 1,
                "username": "email_user",
                "email": "email_user@example.com",
                "role": "user",
                "status": "active",
                "is_verified": True,
                "login_count": 0,
                "failed_attempts": 0,
                "total_online_seconds": 0,
                "created_at": None,
                "updated_at": None,
                "last_login_at": None,
                "last_login_ip": None,
                "bio": None,
                "avatar_url": None,
                "birthday": None,
                "gender": None,
                "occupation": None,
                "education": None,
                "university": None,
                "location": None,
                "interests": None,
                "preferred_language": None,
                "timezone": None,
            },
        )()
        mock_complete_email_registration.return_value = user

        response = self.client.post(
            "/api/auth/complete-email-registration",
            json={
                "token": "ready-token",
                "username": "email_user",
                "password": "secret123",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["username"], "email_user")
        self.assertEqual(body["email"], "email_user@example.com")
        self.assertNotIn("session_id", body)
        mock_complete_email_registration.assert_called_once()

    @patch("app.routes.auth.service.verify_email_token")
    def test_verify_email_marks_account_verified(self, mock_verify_email_token):
        mock_verify_email_token.return_value = type(
            "UserStub",
            (),
            {"email": "ok@example.com", "username": "ok_user"},
        )()

        response = self.client.get("/api/auth/verify-email?token=email-token")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "邮箱验证成功：ok_user")
        mock_verify_email_token.assert_called_once_with(unittest.mock.ANY, "email-token")


if __name__ == "__main__":
    unittest.main()
