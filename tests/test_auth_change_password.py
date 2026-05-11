import unittest
from datetime import datetime, timedelta, UTC

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.auth.core import service, utils
from app.service.auth.database.models import Base, User, UserAuthIdentity, Session, RefreshToken


class ChangePasswordTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = session_local()
        self.user = self._seed_user_with_sessions()

    def tearDown(self):
        self.db.close()

    def _seed_user_with_sessions(self):
        user = User(
            username="tester",
            email="tester@example.com",
            hashed_password=utils.get_password_hash("old-password"),
            role="user",
            status="active",
            is_verified=True,
            failed_attempts=3,
            last_failed_login=datetime.now(UTC).replace(tzinfo=None),
            total_online_seconds=0,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.db.add(user)
        self.db.flush()

        self.db.add(UserAuthIdentity(
            user_id=user.id,
            provider="email",
            identifier_normalized="tester@example.com",
            email="tester@example.com",
            display_name="tester@example.com",
            is_verified=True,
            is_primary=True,
        ))

        now = datetime.now(UTC).replace(tzinfo=None)
        keep_session = Session(
            session_id="keep-session",
            user_id=user.id,
            username=user.username,
            created_at=now,
            expires_at=now + timedelta(days=7),
            last_activity_at=now,
            revoked=False,
            first_ip="127.0.0.1",
            current_ip="127.0.0.1",
        )
        other_session = Session(
            session_id="other-session",
            user_id=user.id,
            username=user.username,
            created_at=now,
            expires_at=now + timedelta(days=7),
            last_activity_at=now,
            revoked=False,
            first_ip="127.0.0.2",
            current_ip="127.0.0.2",
        )
        self.db.add_all([keep_session, other_session])
        self.db.flush()

        self.db.add_all([
            RefreshToken(
                token="keep-token",
                session_id=keep_session.id,
                user_id=user.id,
                expires_at=now + timedelta(days=7),
                revoked=False,
                ip_address="127.0.0.1",
                device_info="browser-a",
            ),
            RefreshToken(
                token="other-token",
                session_id=other_session.id,
                user_id=user.id,
                expires_at=now + timedelta(days=7),
                revoked=False,
                ip_address="127.0.0.2",
                device_info="browser-b",
            ),
        ])
        self.db.commit()
        self.db.refresh(user)
        return user

    def test_change_password_revokes_other_sessions_but_keeps_current_one(self):
        service.change_password(
            self.db,
            self.user,
            current_password="old-password",
            new_password="new-password-123",
            revoke_other_sessions=True,
            current_session_public_id="keep-session",
        )

        refreshed_user = self.db.query(User).filter(User.id == self.user.id).first()
        keep_session = self.db.query(Session).filter(Session.session_id == "keep-session").first()
        other_session = self.db.query(Session).filter(Session.session_id == "other-session").first()
        other_token = self.db.query(RefreshToken).filter(RefreshToken.token == "other-token").first()

        self.assertTrue(utils.verify_password("new-password-123", refreshed_user.hashed_password))
        self.assertEqual(refreshed_user.failed_attempts, 0)
        self.assertIsNone(refreshed_user.last_failed_login)
        self.assertFalse(keep_session.revoked)
        self.assertTrue(other_session.revoked)
        self.assertEqual(other_session.revoked_reason, "password_change_other_sessions")
        self.assertTrue(other_token.revoked)

    def test_change_password_rejects_same_new_password(self):
        with self.assertRaisesRegex(ValueError, "新密码不能与当前密码相同"):
            service.change_password(
                self.db,
                self.user,
                current_password="old-password",
                new_password="old-password",
                revoke_other_sessions=False,
                current_session_public_id="keep-session",
            )


if __name__ == "__main__":
    unittest.main()
