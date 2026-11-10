from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.service.auth.database.models import Base, PasswordResetMailbox
from app.service.auth import password_reset_mailbox as worker
from app.service.auth.password_reset_mail import MailVerificationTemporaryError


class FakeIMAP:
    def __init__(self, *args, **kwargs):
        self.readonly = None
        self.fetches = []
        self.size = 100
        self.uids = b'1 2 3'
        self.next_uid = b'4'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def login(self, *args):
        return 'OK', []

    def select(self, *args, readonly=False):
        self.readonly = readonly
        return 'OK', []

    def response(self, name):
        return name, [self.next_uid if name == 'UIDNEXT' else b'12345']

    def uid(self, command, *args):
        if command == 'search':
            return 'OK', [self.uids]
        self.fetches.append(args)
        if args[1] == '(RFC822.SIZE)':
            return 'OK', [f'1 (RFC822.SIZE {self.size})'.encode()]
        return 'OK', [(b'header', b'raw signed mail')]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + str(tmp_path / 'test.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    imap = FakeIMAP()
    apply = Mock(return_value=True)
    monkeypatch.setattr(worker, 'apply_request', apply)
    monkeypatch.setattr(worker, 'authenticated_request', lambda raw: ('owner@gmail.com', 'a' * 43))
    yield factory, imap, apply
    engine.dispose()


def test_poll_is_readonly_bounded_and_resumes_without_reprocessing(setup):
    factory, imap, apply = setup
    assert worker.poll_mailbox(factory, 'not-a-real-secret', imap_factory=lambda *a, **kw: imap) == 3
    assert imap.readonly is True
    assert apply.call_count == 3
    assert worker.poll_mailbox(factory, 'not-a-real-secret', imap_factory=lambda *a, **kw: imap) == 0
    assert apply.call_count == 3
    with factory() as db:
        assert db.get(PasswordResetMailbox, worker.RECIPIENT).last_uid == 3


def test_dns_outage_keeps_cursor_for_retry(setup, monkeypatch):
    factory, imap, apply = setup
    def unavailable(raw):
        raise MailVerificationTemporaryError('temporary')
    monkeypatch.setattr(worker, 'authenticated_request', unavailable)
    with pytest.raises(MailVerificationTemporaryError):
        worker.poll_mailbox(factory, 'not-a-real-secret', imap_factory=lambda *a, **kw: imap)
    apply.assert_not_called()
    with factory() as db:
        assert db.get(PasswordResetMailbox, worker.RECIPIENT).last_uid == 0


def test_oversized_mail_is_not_downloaded_or_processed(setup):
    factory, imap, apply = setup
    imap.size = 256 * 1024 + 1
    assert worker.poll_mailbox(factory, 'not-a-real-secret', imap_factory=lambda *a, **kw: imap) == 0
    assert all(args[1] == '(RFC822.SIZE)' for args in imap.fetches)
    apply.assert_not_called()


def test_large_backlog_is_processed_in_bounded_batches(setup):
    factory, imap, apply = setup
    imap.uids = b' '.join(str(i).encode() for i in range(1, 101))
    imap.next_uid = b'101'
    assert worker.poll_mailbox(factory, 'not-a-real-secret', imap_factory=lambda *a, **kw: imap) == 8
    assert apply.call_count == 8
    with factory() as db:
        assert db.get(PasswordResetMailbox, worker.RECIPIENT).last_uid == 8


def test_empty_search_advances_past_unrelated_messages(setup):
    factory, imap, apply = setup
    imap.uids = b''
    assert worker.poll_mailbox(factory, 'not-a-real-secret', imap_factory=lambda *a, **kw: imap) == 0
    with factory() as db:
        assert db.get(PasswordResetMailbox, worker.RECIPIENT).last_uid == 3
    apply.assert_not_called()
