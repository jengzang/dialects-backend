import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.auth.core import service, utils, wechat_mini_service
from app.service.auth.database.models import Base, Session, User, UserAuthIdentity


class WechatMiniServiceTests(unittest.TestCase):
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
            username="wechat_mini_owner",
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

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_prepare_wechat_mini_auth_returns_register_for_new_identity(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.return_value = {
            "openid": "mini-openid-001",
            "unionid": "mini-unionid-001",
        }

        result = wechat_mini_service.prepare_wechat_mini_auth(self.db, code="mini-code-001")

        self.assertEqual(result["action"], "register")
        self.assertEqual(result["payload"]["openid"], "mini-openid-001")
        self.assertEqual(result["suggested_username"], "wechat_mini_openid_001")

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_prepare_wechat_mini_auth_wraps_client_error_as_value_error(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.side_effect = wechat_mini_service.WechatMiniClientError("WeChat Mini code2session 请求失败")

        with self.assertRaisesRegex(ValueError, "WeChat Mini code2session 请求失败"):
            wechat_mini_service.prepare_wechat_mini_auth(self.db, code="mini-code-error")

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_register_user_with_wechat_mini_wraps_client_error_as_value_error(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.side_effect = wechat_mini_service.WechatMiniClientError("WeChat Mini appid/appsecret 未配置")
        signup = type("WechatMiniSignup", (), {
            "code": "mini-code-config-error",
            "username": "wechat_mini_error_user",
            "password": "secret123",
        })()

        with self.assertRaisesRegex(ValueError, "WeChat Mini appid/appsecret 未配置"):
            wechat_mini_service.register_user_with_wechat_mini(self.db, signup, register_ip="127.0.0.1")

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_prepare_wechat_mini_auth_returns_login_for_existing_identity(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.return_value = {
            "openid": "mini-openid-002-new",
            "unionid": "mini-unionid-002",
        }
        self.db.add(UserAuthIdentity(
            user_id=self.user.id,
            provider="wechat_mini",
            identifier_normalized="mini-openid-002-old",
            provider_subject="mini-unionid-002",
            display_name="Mini User",
            is_verified=False,
            is_primary=False,
        ))
        self.db.commit()

        result = wechat_mini_service.prepare_wechat_mini_auth(self.db, code="mini-code-002")

        self.assertEqual(result["action"], "login")
        self.assertEqual(result["user"].id, self.user.id)
        identity = service.get_identity_by_provider_subject(self.db, "wechat_mini", "mini-unionid-002")
        self.assertEqual(identity.identifier_normalized, "mini-openid-002-new")
        self.assertTrue(identity.is_verified)

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_register_user_with_wechat_mini_creates_user_and_provider_identity(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.return_value = {
            "openid": "mini-openid-003",
            "unionid": "mini-unionid-003",
        }
        signup = type("WechatMiniSignup", (), {
            "code": "mini-code-003",
            "username": "wechat_mini_new_user",
            "password": "secret123",
        })()

        user, identity = wechat_mini_service.register_user_with_wechat_mini(self.db, signup, register_ip="127.0.0.1")

        self.assertEqual(user.username, "wechat_mini_new_user")
        self.assertIsNone(user.email)
        self.assertTrue(user.is_verified)
        self.assertEqual(identity.provider, "wechat_mini")
        self.assertEqual(identity.provider_subject, "mini-unionid-003")
        self.assertEqual(identity.identifier_normalized, "mini-openid-003")

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_register_user_with_wechat_mini_rejects_existing_provider_link(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.return_value = {
            "openid": "mini-openid-004",
            "unionid": "mini-unionid-004",
        }
        self.db.add(UserAuthIdentity(
            user_id=self.user.id,
            provider="wechat_mini",
            identifier_normalized="mini-openid-004",
            provider_subject="mini-unionid-004",
            display_name="Mini User",
            is_verified=True,
            is_primary=False,
        ))
        self.db.commit()
        signup = type("WechatMiniSignup", (), {
            "code": "mini-code-004",
            "username": "wechat_mini_dupe",
            "password": "secret123",
        })()

        with self.assertRaises(service.AuthConflictError) as ctx:
            wechat_mini_service.register_user_with_wechat_mini(self.db, signup, register_ip="127.0.0.1")

        self.assertEqual(ctx.exception.conflict_code, service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED)

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_bind_wechat_mini_identity_rejects_stale_session(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.return_value = {
            "openid": "mini-openid-stale",
            "unionid": "mini-unionid-stale",
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
            wechat_mini_service.bind_wechat_mini_identity(
                self.db,
                self.user,
                code="mini-code-stale",
                current_session_public_id="stale-session",
            )

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_bind_wechat_mini_identity_requires_rebind_when_current_account_has_other_mini(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.return_value = {
            "openid": "mini-openid-005-new",
            "unionid": "mini-unionid-005-new",
        }
        self.db.add(UserAuthIdentity(
            user_id=self.user.id,
            provider="wechat_mini",
            identifier_normalized="mini-openid-005-old",
            provider_subject="mini-unionid-005-old",
            display_name="Mini User",
            is_verified=True,
            is_primary=False,
        ))
        self.db.commit()

        with self.assertRaises(service.AuthConflictError) as ctx:
            wechat_mini_service.bind_wechat_mini_identity(
                self.db,
                self.user,
                code="mini-code-005",
                current_session_public_id="fresh-session",
            )

        self.assertEqual(ctx.exception.conflict_code, service.CONFLICT_CODE_CURRENT_ACCOUNT_PROVIDER_MISMATCH)
        self.assertEqual(ctx.exception.suggested_action, service.SUGGESTED_ACTION_REPLACE_EXISTING_PROVIDER_BINDING)

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_bind_wechat_mini_identity_rejects_provider_linked_to_another_account(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.return_value = {
            "openid": "mini-openid-006",
            "unionid": "mini-unionid-006",
        }
        other_user = User(
            username="other_mini_user",
            email="other@example.com",
            hashed_password=utils.get_password_hash("secret123"),
            role="user",
            status="active",
            is_verified=True,
            failed_attempts=0,
            total_online_seconds=0,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.db.add(other_user)
        self.db.flush()
        self.db.add(UserAuthIdentity(
            user_id=other_user.id,
            provider="wechat_mini",
            identifier_normalized="mini-openid-006",
            provider_subject="mini-unionid-006",
            display_name="Other Mini User",
            is_verified=True,
            is_primary=False,
        ))
        self.db.commit()

        with self.assertRaises(service.AuthConflictError) as ctx:
            wechat_mini_service.bind_wechat_mini_identity(
                self.db,
                self.user,
                code="mini-code-006",
                current_session_public_id="fresh-session",
            )

        self.assertEqual(ctx.exception.conflict_code, service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED)

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_rebind_wechat_mini_identity_updates_existing_identity(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.return_value = {
            "openid": "mini-openid-007-new",
            "unionid": "mini-unionid-007-new",
        }
        self.db.add(UserAuthIdentity(
            user_id=self.user.id,
            provider="wechat_mini",
            identifier_normalized="mini-openid-007-old",
            provider_subject="mini-unionid-007-old",
            display_name="Mini User",
            is_verified=False,
            is_primary=False,
        ))
        self.db.commit()

        identity = wechat_mini_service.rebind_wechat_mini_identity(
            self.db,
            self.user,
            code="mini-code-007",
            current_session_public_id="fresh-session",
        )

        self.assertEqual(identity.provider_subject, "mini-unionid-007-new")
        self.assertEqual(identity.identifier_normalized, "mini-openid-007-new")
        self.assertTrue(identity.is_verified)
        self.assertIsNotNone(identity.last_login_at)

    @patch("app.service.auth.core.wechat_mini_service.exchange_code_for_session")
    def test_rebind_wechat_mini_identity_rejects_provider_linked_to_another_account(self, mock_exchange_code_for_session):
        mock_exchange_code_for_session.return_value = {
            "openid": "mini-openid-008",
            "unionid": "mini-unionid-008",
        }
        other_user = User(
            username="other_mini_user_two",
            email="other2@example.com",
            hashed_password=utils.get_password_hash("secret123"),
            role="user",
            status="active",
            is_verified=True,
            failed_attempts=0,
            total_online_seconds=0,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.db.add(other_user)
        self.db.flush()
        self.db.add(UserAuthIdentity(
            user_id=other_user.id,
            provider="wechat_mini",
            identifier_normalized="mini-openid-008",
            provider_subject="mini-unionid-008",
            display_name="Other Mini User",
            is_verified=True,
            is_primary=False,
        ))
        self.db.commit()

        with self.assertRaises(service.AuthConflictError) as ctx:
            wechat_mini_service.rebind_wechat_mini_identity(
                self.db,
                self.user,
                code="mini-code-008",
                current_session_public_id="fresh-session",
            )

        self.assertEqual(ctx.exception.conflict_code, service.CONFLICT_CODE_PROVIDER_ALREADY_LINKED)


if __name__ == "__main__":
    unittest.main()
