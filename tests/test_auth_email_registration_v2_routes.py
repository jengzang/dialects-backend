import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.auth.core import service
from app.service.auth.database.models import Base, User, UserAuthIdentity


class EmailRegistrationV2RouteSupportTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()

    def tearDown(self):
        self.db.close()

    @patch("app.service.auth.core.service.send_verification_email")
    def test_start_email_registration_uses_verify_url_argument(self, mock_send_verification_email):
        token = service.start_email_registration(
            self.db,
            email="fresh@example.com",
            requested_ip="127.0.0.1",
            verify_url="https://frontend.example/verify?token={token}",
        )
        self.assertTrue(token)
        mock_send_verification_email.assert_called_once()
        sent_verify_url = mock_send_verification_email.call_args.args[2]
        self.assertIn("https://frontend.example/verify?token=", sent_verify_url)

    def test_verify_then_complete_email_registration_roundtrip(self):
        token = service.issue_email_registration_token(
            self.db,
            email="verified@example.com",
            requested_ip="127.0.0.1",
        )
        verification = service.verify_email_registration_token(self.db, token)
        self.assertEqual(verification["email"], "verified@example.com")
        self.assertTrue(verification["ready_to_complete"])

        user = service.complete_email_registration(
            self.db,
            token=token,
            username="verified_user",
            password="secret123",
            register_ip="127.0.0.1",
        )
        self.assertEqual(user.username, "verified_user")
        self.assertEqual(user.email, "verified@example.com")

        identity = self.db.query(UserAuthIdentity).filter(
            UserAuthIdentity.user_id == user.id,
            UserAuthIdentity.provider == "email",
        ).one()
        self.assertTrue(identity.is_verified)
        self.assertTrue(identity.is_primary)

    def test_existing_email_is_rejected(self):
        now = datetime.now(UTC).replace(tzinfo=None)
        user = User(
            username="existing_user",
            email="taken@example.com",
            hashed_password="hashed",
            role="user",
            status="active",
            is_verified=True,
            failed_attempts=0,
            total_online_seconds=0,
            created_at=now,
        )
        self.db.add(user)
        self.db.flush()
        self.db.add(UserAuthIdentity(
            user_id=user.id,
            provider="email",
            identifier_normalized="taken@example.com",
            email="taken@example.com",
            display_name="taken@example.com",
            is_verified=True,
            is_primary=True,
        ))
        self.db.commit()

        with patch("app.service.auth.core.service.send_verification_email"):
            with self.assertRaisesRegex(ValueError, "该邮箱已被其他账号占用"):
                service.start_email_registration(
                    self.db,
                    email="taken@example.com",
                    requested_ip="127.0.0.1",
                    verify_url="https://frontend.example/verify?token={token}",
                )


if __name__ == "__main__":
    unittest.main()
