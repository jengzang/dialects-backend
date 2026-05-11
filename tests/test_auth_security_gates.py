import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.auth.core import service, utils
from app.service.auth.database.models import Base, Session, User, UserAuthIdentity


class AuthSecurityGateTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()
        self.user = self._seed_user()
        self.google_identity = self._seed_google_identity()

    def tearDown(self):
        self.db.close()

    def _seed_user(self):
        now = datetime.now(UTC).replace(tzinfo=None)
        user = User(
            username="security_tester",
            email="security@example.com",
            hashed_password=utils.get_password_hash("old-password"),
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
            identifier_normalized="security@example.com",
            email="security@example.com",
            display_name="security@example.com",
            is_verified=True,
            is_primary=True,
        ))

        fresh_session = Session(
            session_id="fresh-session",
            user_id=user.id,
            username=user.username,
            created_at=now,
            expires_at=now + timedelta(days=7),
            last_activity_at=now,
            revoked=False,
            first_ip="127.0.0.1",
            current_ip="127.0.0.1",
        )
        stale_session = Session(
            session_id="stale-session",
            user_id=user.id,
            username=user.username,
            created_at=now - timedelta(hours=3),
            expires_at=now + timedelta(days=7),
            last_activity_at=now - timedelta(hours=2),
            revoked=False,
            first_ip="127.0.0.2",
            current_ip="127.0.0.2",
        )
        self.db.add_all([fresh_session, stale_session])
        self.db.commit()
        self.db.refresh(user)
        return user

    def _seed_google_identity(self):
        identity = UserAuthIdentity(
            user_id=self.user.id,
            provider="google",
            provider_subject="seed-google-sub",
            identifier_normalized="security@gmail.com",
            email="security@gmail.com",
            display_name="Security Tester",
            is_verified=True,
            is_primary=False,
        )
        self.db.add(identity)
        self.db.commit()
        self.db.refresh(identity)
        return identity

    def test_change_primary_email_rejects_wrong_current_password(self):
        with self.assertRaisesRegex(ValueError, "当前密码错误"):
            service.change_primary_email(
                self.db,
                self.user,
                "next@example.com",
                current_password="wrong-password",
            )

    @patch("app.service.auth.core.utils.verify_google_id_token")
    def test_bind_google_identity_rejects_stale_session(self, mock_verify_google_id_token):
        mock_verify_google_id_token.return_value = {
            "sub": "google-sub-123456",
            "email": "security@gmail.com",
            "name": "Security Tester",
            "picture": "https://example.com/avatar.png",
        }

        with self.assertRaisesRegex(ValueError, "需要近期重新验证"):
            service.bind_google_identity(
                self.db,
                self.user,
                "x" * 30,
                current_session_public_id="stale-session",
            )

    def test_unbind_google_identity_is_forbidden_in_v1(self):
        with self.assertRaisesRegex(ValueError, "仅支持换绑"):
            service.unbind_auth_provider(self.db, self.user, "google")

    def test_provider_list_exposes_rebind_not_unbind_capabilities(self):
        providers = service.list_auth_providers(self.db, self.user)
        provider_by_name = {item["provider"]: item for item in providers}

        self.assertFalse(provider_by_name["email"]["can_unbind"])
        self.assertTrue(provider_by_name["email"]["can_replace"])
        self.assertEqual(provider_by_name["email"]["replacement_action"], "change_email")

        self.assertFalse(provider_by_name["google"]["can_unbind"])
        self.assertTrue(provider_by_name["google"]["can_replace"])
        self.assertEqual(provider_by_name["google"]["replacement_action"], "bind_google")


if __name__ == "__main__":
    unittest.main()
