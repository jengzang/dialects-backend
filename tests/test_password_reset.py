import os
from datetime import datetime, timedelta

os.environ.setdefault('_RUN_TYPE', 'WEB')
os.environ.setdefault('AUTO_MIGRATE', 'false')

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.auth.database.models import Base, User, Session, RefreshToken
from app.service.auth.core.utils import get_password_hash, verify_password
from app.service.auth.password_reset import create_request, apply_request, ResetRateLimit


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        yield db
    engine.dispose()


def account(db):
    user = User(username='reset-test', email='owner@qq.com', hashed_password=get_password_hash('original-secret'))
    db.add(user)
    db.commit()
    return user


def test_request_waits_for_mail_and_never_stores_plaintext(db):
    user = account(db)
    request = create_request(db, user.email, 'replacement-secret', '127.0.0.1')
    assert len(request['request_id']) >= 32
    assert request['expires_in'] == 1800
    assert verify_password('original-secret', user.hashed_password)
    from app.service.auth.database.models import PasswordResetRequest
    row = db.query(PasswordResetRequest).one()
    assert row.token_hash != request['request_id']
    assert verify_password('replacement-secret', row.password_hash)


def test_verified_matching_mail_changes_password_once_and_revokes_sessions(db):
    user = account(db)
    now = datetime.utcnow()
    session = Session(session_id='existing', user_id=user.id, username=user.username,
                      expires_at=now + timedelta(days=1), first_ip='127.0.0.1', current_ip='127.0.0.1')
    db.add(session)
    db.flush()
    refresh = RefreshToken(token='old-refresh', user_id=user.id, session_id=session.id,
                           expires_at=now + timedelta(days=1))
    db.add(refresh)
    db.commit()
    request = create_request(db, user.email, 'replacement-secret', '127.0.0.1')
    assert apply_request(db, request['request_id'], user.email) is True
    db.refresh(user)
    db.refresh(session)
    db.refresh(refresh)
    assert verify_password('replacement-secret', user.hashed_password)
    assert session.revoked and refresh.revoked
    assert apply_request(db, request['request_id'], user.email) is False


@pytest.mark.parametrize('change', ['wrong_sender', 'expired', 'password_changed', 'email_changed', 'disabled'])
def test_invalid_or_stale_request_never_changes_password(db, change):
    user = account(db)
    now = datetime.utcnow()
    request = create_request(db, user.email, 'replacement-secret', '127.0.0.1', now=now)
    sender = user.email
    if change == 'wrong_sender':
        sender = 'attacker@qq.com'
    elif change == 'expired':
        now += timedelta(minutes=31)
    elif change == 'password_changed':
        user.hashed_password = get_password_hash('another-secret')
    elif change == 'email_changed':
        user.email = 'changed@qq.com'
    elif change == 'disabled':
        user.status = 'disabled'
    db.commit()
    previous = user.hashed_password
    assert apply_request(db, request['request_id'], sender, now=now) is False
    db.refresh(user)
    assert user.hashed_password == previous


def test_unknown_email_has_same_response_shape_and_cannot_reset(db):
    result = create_request(db, 'missing@qq.com', 'replacement-secret', '127.0.0.1')
    assert set(result) == {'request_id', 'expires_in', 'recipient'}
    assert apply_request(db, result['request_id'], 'missing@qq.com') is False


def test_new_request_does_not_cancel_old_request_but_success_does(db):
    user = account(db)
    first = create_request(db, user.email, 'first-secret', '127.0.0.1')
    second = create_request(db, user.email, 'second-secret', '127.0.0.1')
    assert apply_request(db, first['request_id'], user.email)
    assert not apply_request(db, second['request_id'], user.email)


def test_rate_limits_before_expensive_hashing(db):
    for _ in range(3):
        create_request(db, 'missing@qq.com', 'replacement-secret', '127.0.0.1')
    with pytest.raises(ResetRateLimit):
        create_request(db, 'missing@qq.com', 'replacement-secret', '127.0.0.1')


@pytest.mark.parametrize('password', ['short', 'a' * 73, '密' * 25])
def test_password_rejects_weak_or_bcrypt_truncated_values(db, password):
    with pytest.raises(ValueError):
        create_request(db, 'owner@qq.com', password, '127.0.0.1')


def test_concurrent_delivery_only_changes_password_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    engine = create_engine('sqlite:///' + str(tmp_path / 'concurrent.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        user = account(db)
        request = create_request(db, user.email, 'replacement-secret', '127.0.0.1')
    def deliver(_):
        with factory() as db:
            return apply_request(db, request['request_id'], 'owner@qq.com')
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(deliver, range(2))) == 1
    engine.dispose()


def test_failed_session_revocation_rolls_back_password_and_consumption(db):
    from sqlalchemy import event
    from app.service.auth.database.models import PasswordResetRequest
    user = account(db)
    request = create_request(db, user.email, 'replacement-secret', '127.0.0.1')
    def fail_revocation(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('UPDATE sessions'):
            raise RuntimeError('simulated revocation failure')
    event.listen(db.bind, 'before_cursor_execute', fail_revocation)
    try:
        with pytest.raises(RuntimeError):
            apply_request(db, request['request_id'], 'owner@qq.com')
    finally:
        event.remove(db.bind, 'before_cursor_execute', fail_revocation)
    db.refresh(user)
    assert verify_password('original-secret', user.hashed_password)
    assert db.query(PasswordResetRequest).one().consumed_at is None


def test_reset_requests_do_not_block_existing_account_deletion(db):
    from sqlalchemy import text
    from app.service.auth.database.models import PasswordResetRequest
    db.execute(text('PRAGMA foreign_keys=ON'))
    user = account(db)
    create_request(db, user.email, 'replacement-secret', '127.0.0.1')
    db.delete(user)
    db.commit()
    assert db.query(PasswordResetRequest).count() == 0
