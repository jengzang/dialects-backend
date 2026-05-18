import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.auth.core import service, utils
from app.service.auth.database.models import Base, Session, User, UserAuthIdentity, AuthActionToken


class OAuthStateAndCallbackTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()
        if not hasattr(AuthActionToken, "metadata_json"):
            setattr(AuthActionToken, "metadata_json", None)
        self.user = self._seed_user()

    def tearDown(self):
        self.db.close()

    def _seed_user(self):
        now = datetime.now(UTC).replace(tzinfo=None)
        user = User(
            username="oauth_owner",
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

    def test_issue_and_consume_google_login_oauth_state(self):
        state, expires_at = service.issue_oauth_state(
            self.db,
            provider=service.OAUTH_PROVIDER_GOOGLE,
            intent=service.OAUTH_INTENT_LOGIN_OR_REGISTER,
            requested_ip="127.0.0.1",
            redirect_uri="https://frontend.example/google/callback",
        )
        self.assertTrue(state)
        self.assertGreater(expires_at, utils.now_utc_naive())

        record = service.consume_oauth_state(
            self.db,
            provider=service.OAUTH_PROVIDER_GOOGLE,
            intent=service.OAUTH_INTENT_LOGIN_OR_REGISTER,
            state=state,
        )
        self.assertEqual(record.requested_ip, "127.0.0.1")
        self.assertEqual(record.target_email, "https://frontend.example/google/callback")
        self.assertIsNotNone(record.consumed_at)

        with self.assertRaisesRegex(ValueError, "OAuth state 无效或已过期"):
            service.consume_oauth_state(
                self.db,
                provider=service.OAUTH_PROVIDER_GOOGLE,
                intent=service.OAUTH_INTENT_LOGIN_OR_REGISTER,
                state=state,
            )

    @patch("app.service.auth.core.utils.verify_google_id_token")
    def test_complete_google_oauth_callback_returns_register_payload(self, mock_verify_google_id_token):
        start = service.start_google_oauth(
            self.db,
            intent=service.OAUTH_INTENT_LOGIN_OR_REGISTER,
            requested_ip="127.0.0.1",
            redirect_uri="https://frontend.example/google/callback",
        )
        mock_verify_google_id_token.return_value = {
            "sub": "google-sub-new",
            "email": "newgoogle@example.com",
            "email_verified": True,
            "name": "Google New",
            "picture": "https://example.com/google.png",
        }

        result = service.complete_google_oauth_callback(
            self.db,
            state=start["state"],
            id_token="x" * 30,
        )
        self.assertEqual(result["action"], "register")
        self.assertEqual(result["email"], "newgoogle@example.com")
        self.assertEqual(result["suggested_username"], "newgoogle_example_com")

    @patch("app.service.auth.core.utils.verify_google_id_token")
    def test_complete_google_oauth_callback_login_creates_real_session_tokens(self, mock_verify_google_id_token):
        self.db.add(UserAuthIdentity(
            user_id=self.user.id,
            provider="google",
            provider_subject="google-sub-owner",
            identifier_normalized="owner@example.com",
            email="owner@example.com",
            display_name="Owner Google",
            is_verified=True,
            is_primary=False,
        ))
        self.db.commit()
        start = service.start_google_oauth(
            self.db,
            intent=service.OAUTH_INTENT_LOGIN_OR_REGISTER,
            requested_ip="127.0.0.1",
            redirect_uri="https://frontend.example/google/callback",
        )
        mock_verify_google_id_token.return_value = {
            "sub": "google-sub-owner",
            "email": "owner@example.com",
            "email_verified": True,
            "name": "Owner Google",
            "picture": "https://example.com/owner.png",
        }

        result = service.complete_google_oauth_callback(
            self.db,
            state=start["state"],
            id_token="x" * 30,
        )
        self.assertEqual(result["action"], "login")
        self.assertTrue(result["session_id"])
        payload = utils.decode_access_token(result["access_token"])
        self.assertEqual(payload.get("session_id"), result["session_id"])
        self.assertIsNotNone(self.db.query(Session).filter(Session.session_id == result["session_id"]).first())

    @patch("app.service.auth.core.utils.verify_google_id_token")
    def test_complete_google_bind_callback_invalid_session_keeps_state_reusable(self, mock_verify_google_id_token):
        start = service.start_google_oauth(
            self.db,
            intent=service.OAUTH_INTENT_BIND,
            requested_ip="127.0.0.1",
            redirect_uri="https://frontend.example/google/callback",
            current_user=self.user,
            current_session_public_id="missing-session",
        )
        mock_verify_google_id_token.return_value = {
            "sub": "google-sub-bind",
            "email": "bind@example.com",
            "email_verified": True,
            "name": "Bind Google",
            "picture": None,
        }

        with self.assertRaisesRegex(ValueError, "当前登录态已失效"):
            service.complete_google_oauth_callback(
                self.db,
                state=start["state"],
                id_token="x" * 30,
            )

        record = service.consume_oauth_state(
            self.db,
            provider=service.OAUTH_PROVIDER_GOOGLE,
            intent=service.OAUTH_INTENT_BIND,
            state=start["state"],
        )
        self.assertIsNotNone(record)

    @patch("app.service.auth.core.utils.verify_google_id_token")
    def test_complete_google_oauth_callback_conflict_raises_structured_error(self, mock_verify_google_id_token):
        start = service.start_google_oauth(
            self.db,
            intent=service.OAUTH_INTENT_LOGIN_OR_REGISTER,
            requested_ip="127.0.0.1",
            redirect_uri="https://frontend.example/google/callback",
        )
        mock_verify_google_id_token.return_value = {
            "sub": "google-sub-conflict",
            "email": "owner@example.com",
            "email_verified": True,
            "name": "Conflict Google",
            "picture": None,
        }

        with self.assertRaises(service.AuthConflictError) as ctx:
            service.complete_google_oauth_callback(self.db, state=start["state"], id_token="x" * 30)

        self.assertEqual(ctx.exception.conflict_code, service.CONFLICT_CODE_EMAIL_ALREADY_EXISTS)
        self.assertEqual(ctx.exception.suggested_action, service.SUGGESTED_ACTION_LOGIN_THEN_BIND)

    @patch("app.service.auth.core.utils.verify_wechat_access_token")
    def test_complete_wechat_bind_callback_binds_identity(self, mock_verify_wechat_access_token):
        start = service.start_wechat_oauth(
            self.db,
            intent=service.OAUTH_INTENT_BIND,
            requested_ip="127.0.0.1",
            redirect_uri="https://frontend.example/wechat/callback",
            current_user=self.user,
            current_session_public_id="fresh-session",
        )
        mock_verify_wechat_access_token.return_value = {
            "openid": "wechat-openid-bind",
            "unionid": "wechat-unionid-bind",
            "nickname": "绑定微信",
            "headimgurl": "https://example.com/wechat.png",
        }

        result = service.complete_wechat_oauth_callback(
            self.db,
            state=start["state"],
            access_token="token",
            openid="wechat-openid-bind",
        )
        self.assertEqual(result["action"], "bound")
        self.assertEqual(result["provider"], "wechat")
        self.assertEqual(result["provider_subject"], "wechat-unionid-bind")

    def test_bind_oauth_state_requires_user(self):
        with self.assertRaisesRegex(ValueError, "绑定场景必须提供当前用户"):
            service.issue_oauth_state(
                self.db,
                provider=service.OAUTH_PROVIDER_GOOGLE,
                intent=service.OAUTH_INTENT_BIND,
                requested_ip="127.0.0.1",
                redirect_uri="https://frontend.example/google/callback",
                current_user=None,
            )


if __name__ == "__main__":
    unittest.main()
