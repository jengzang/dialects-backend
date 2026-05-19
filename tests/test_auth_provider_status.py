import unittest
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.auth.core import service
from app.service.auth.database.models import Base, User, UserAuthIdentity


class AuthProviderStatusTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()
        now = datetime.now(UTC).replace(tzinfo=None)
        self.user = User(
            username="provider_user",
            email="provider@example.com",
            hashed_password="hashed",
            role="user",
            status="active",
            is_verified=True,
            failed_attempts=0,
            total_online_seconds=0,
            created_at=now,
        )
        self.db.add(self.user)
        self.db.flush()
        self.db.add_all([
            UserAuthIdentity(
                user_id=self.user.id,
                provider="email",
                identifier_normalized="provider@example.com",
                email="provider@example.com",
                display_name="provider@example.com",
                is_verified=True,
                is_primary=True,
            ),
            UserAuthIdentity(
                user_id=self.user.id,
                provider="google",
                identifier_normalized="google-subject-old",
                provider_subject="google-subject-old",
                email="provider@example.com",
                display_name="Google User",
                is_verified=True,
                is_primary=False,
            ),
            UserAuthIdentity(
                user_id=self.user.id,
                provider="wechat",
                identifier_normalized="wechat-openid-old",
                provider_subject="wechat-openid-old",
                display_name="Wechat User",
                is_verified=True,
                is_primary=False,
            ),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_list_auth_providers_exposes_replacement_actions(self):
        providers = service.list_auth_providers(self.db, self.user)
        providers_by_name = {item["provider"]: item for item in providers}

        self.assertEqual(providers_by_name["email"]["replacement_action"], "change_email")
        self.assertTrue(providers_by_name["email"]["can_replace"])
        self.assertEqual(providers_by_name["google"]["replacement_action"], "bind_google")
        self.assertTrue(providers_by_name["google"]["can_replace"])
        self.assertEqual(providers_by_name["wechat"]["replacement_action"], "bind_wechat")
        self.assertTrue(providers_by_name["wechat"]["can_replace"])


if __name__ == "__main__":
    unittest.main()
