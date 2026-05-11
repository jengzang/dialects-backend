import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.auth.core import service, utils
from app.service.auth.database.models import Base, Session, User, UserAuthIdentity


class WechatAuthTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()
        self.user = self._seed_user()

    def tearDown(self):
        self.db.close()

    def _seed_user(self):
        now = datetime.now(UTC).replace(tzinfo=None)
        user = User(
            username="wechat_owner",
            email="owner@example.com",
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
            identifier_normalized="owner@example.com",
            email="owner@example.com",
            display_name="owner@example.com",
            is_verified=True,
            is_primary=True,
        ))

        self.db.add(Session(
            session_id="fresh-session",
            user_id=user.id,
            username=user.username,
            created_at=now,
            expires_at=now + timedelta(days=7),
            last_activity_at=now,
            revoked=False,
            first_ip="127.0.0.1",
            current_ip="127.0.0.1",
        ))
        self.db.commit()
        self.db.refresh(user)
        return user

    @patch("app.service.auth.core.utils.verify_wechat_access_token")
    def test_prepare_wechat_auth_returns_register_for_new_identity_without_email(self, mock_verify_wechat_access_token):
        mock_verify_wechat_access_token.return_value = {
            "openid": "wechat-openid-001",
            "unionid": "wechat-unionid-001",
            "nickname": "微信新用户",
            "headimgurl": "https://example.com/wechat.png",
        }

        result = service.prepare_wechat_auth(self.db, access_token="token", openid="wechat-openid-001")

        self.assertEqual(result["action"], "register")
        self.assertEqual(result["payload"]["openid"], "wechat-openid-001")
        self.assertEqual(result["suggested_username"], "wechat_openid_001")

    @patch("app.service.auth.core.utils.verify_wechat_access_token")
    def test_register_user_with_wechat_creates_user_and_provider_identity_without_email(self, mock_verify_wechat_access_token):
        mock_verify_wechat_access_token.return_value = {
            "openid": "wechat-openid-002",
            "unionid": "wechat-unionid-002",
            "nickname": "微信注册用户",
            "headimgurl": "https://example.com/wechat-register.png",
        }

        signup = type("WechatSignup", (), {
            "access_token": "token",
            "openid": "wechat-openid-002",
            "username": "wechat_new_user",
            "password": "secret123",
        })()

        user, identity = service.register_user_with_wechat(self.db, signup, register_ip="127.0.0.1")

        self.assertEqual(user.username, "wechat_new_user")
        self.assertIsNone(user.email)
        self.assertTrue(user.is_verified)
        self.assertEqual(identity.provider, "wechat")
        self.assertEqual(identity.provider_subject, "wechat-unionid-002")
        self.assertEqual(identity.display_name, "微信注册用户")
        self.assertEqual(identity.profile_picture, "https://example.com/wechat-register.png")

    @patch("app.service.auth.core.utils.verify_wechat_access_token")
    def test_bind_wechat_identity_rejects_stale_session(self, mock_verify_wechat_access_token):
        mock_verify_wechat_access_token.return_value = {
            "openid": "wechat-openid-stale",
            "unionid": "wechat-unionid-stale",
            "nickname": "微信过期会话用户",
            "headimgurl": "https://example.com/wechat-stale.png",
        }

        stale_now = datetime.now(UTC).replace(tzinfo=None)
        self.db.add(Session(
            session_id="stale-session",
            user_id=self.user.id,
            username=self.user.username,
            created_at=stale_now - timedelta(hours=3),
            expires_at=stale_now + timedelta(days=7),
            last_activity_at=stale_now - timedelta(hours=2),
            revoked=False,
            first_ip="127.0.0.2",
            current_ip="127.0.0.2",
        ))
        self.db.commit()

        with self.assertRaisesRegex(ValueError, "需要近期重新验证"):
            service.bind_wechat_identity(
                self.db,
                self.user,
                access_token="token",
                openid="wechat-openid-stale",
                current_session_public_id="stale-session",
            )

        mock_verify_wechat_access_token.return_value = {
            "openid": "wechat-openid-003",
            "unionid": "wechat-unionid-003",
            "nickname": "微信绑定用户",
            "headimgurl": "https://example.com/wechat-bind.png",
        }

        identity = service.bind_wechat_identity(
            self.db,
            self.user,
            access_token="token",
            openid="wechat-openid-003",
            current_session_public_id="fresh-session",
        )

        self.assertEqual(identity.provider, "wechat")
        self.assertEqual(identity.provider_subject, "wechat-unionid-003")
        self.assertEqual(identity.display_name, "微信绑定用户")

        providers = service.list_auth_providers(self.db, self.user)
        provider_by_name = {item["provider"]: item for item in providers}
        self.assertIn("wechat", provider_by_name)
        self.assertFalse(provider_by_name["wechat"]["can_unbind"])
        self.assertTrue(provider_by_name["wechat"]["can_replace"])
        self.assertEqual(provider_by_name["wechat"]["replacement_action"], "bind_wechat")

    def test_unbind_wechat_identity_is_forbidden_in_v1(self):
        with self.assertRaisesRegex(ValueError, "仅支持换绑"):
            service.unbind_auth_provider(self.db, self.user, "wechat")


if __name__ == "__main__":
    unittest.main()
