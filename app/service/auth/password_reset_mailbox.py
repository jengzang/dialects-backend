"""Bounded, read-only QQ IMAP polling using the existing scheduler."""
import imaplib
import logging
import os
import re
import ssl
from datetime import datetime, timedelta

from filelock import FileLock, Timeout

from app.service.auth.database.models import PasswordResetMailbox
from app.service.auth.password_reset import RECIPIENT, apply_request, mailbox_enabled
from app.service.auth.password_reset_mail import MAX_MAIL_BYTES, authenticated_request

logger = logging.getLogger(__name__)
BATCH_SIZE = 8
UID_WINDOW = 2000


def _require_ok(result):
    status, data = result
    if status != 'OK':
        raise RuntimeError('Mailbox operation failed')
    return data


def poll_mailbox(session_factory, password, *, imap_factory=imaplib.IMAP4_SSL):
    applied = 0
    with imap_factory('imap.qq.com', 993, ssl_context=ssl.create_default_context(), timeout=15) as mail:
        _require_ok(mail.login(RECIPIENT, password))
        _require_ok(mail.select('INBOX', readonly=True))
        _, validity_data = mail.response('UIDVALIDITY')
        if not validity_data or not validity_data[0]:
            raise RuntimeError('Mailbox UID validity unavailable')
        validity = validity_data[0].decode('ascii')
        _, next_data = mail.response('UIDNEXT')
        if not next_data or not next_data[0]:
            raise RuntimeError('Mailbox next UID unavailable')
        newest_uid = int(next_data[0]) - 1
        with session_factory() as db:
            state = db.get(PasswordResetMailbox, RECIPIENT)
            if state is None:
                state = PasswordResetMailbox(account=RECIPIENT, uidvalidity=validity, last_uid=0)
                db.add(state)
            elif state.uidvalidity != validity:
                state.uidvalidity, state.last_uid = validity, 0
            last_uid = state.last_uid
            db.commit()
        # The fixed ASCII subject avoids reading unrelated personal messages.
        day = datetime.utcnow() - timedelta(days=1)
        month = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')[day.month - 1]
        since = f'{day.day:02d}-{month}-{day.year}'
        if last_uid >= newest_uid:
            return 0
        horizon = min(newest_uid, last_uid + UID_WINDOW)
        data = _require_ok(mail.uid('search', None, 'UID', f'{last_uid + 1}:{horizon}',
                                   'SINCE', since, 'SUBJECT', '"RESET-REQUEST"'))
        matching = sorted(int(uid) for uid in (data[0] or b'').split() if last_uid < int(uid) <= horizon)
        uids = matching[:BATCH_SIZE]
        for uid in uids:
            size_data = _require_ok(mail.uid('fetch', str(uid), '(RFC822.SIZE)'))
            metadata = b' '.join(item for item in size_data if isinstance(item, bytes))
            size = re.search(rb'RFC822.SIZE (\d+)', metadata)
            if not size:
                raise RuntimeError('Mailbox message size unavailable')
            if int(size[1]) <= MAX_MAIL_BYTES:
                parts = _require_ok(mail.uid('fetch', str(uid), '(BODY.PEEK[])'))
                raw = b''.join(part[1] for part in parts if isinstance(part, tuple))
                if not raw:
                    raise RuntimeError('Mailbox message unavailable')
                # Transient DNS/database failures deliberately leave this UID unconsumed.
                request = authenticated_request(raw)
                if request:
                    sender, token = request
                    with session_factory() as db:
                        applied += int(apply_request(db, token, sender))
            with session_factory() as db:
                state = db.get(PasswordResetMailbox, RECIPIENT)
                state.last_uid = uid
                db.commit()
        if len(matching) <= BATCH_SIZE:
            with session_factory() as db:
                state = db.get(PasswordResetMailbox, RECIPIENT)
                state.last_uid = horizon
                db.commit()
    return applied


def poll_configured_mailbox():
    if not mailbox_enabled():
        return
    from app.common.path import USER_DATABASE_PATH
    from app.service.auth.database.connection import SessionLocal

    # Shared by all workers on this server, without adding a daemon or a thread.
    try:
        with FileLock(str(USER_DATABASE_PATH) + '.password-reset.lock', timeout=0):
            count = poll_mailbox(SessionLocal, os.environ['PASSWORD_RESET_IMAP_PASSWORD'])
            if count:
                logger.info('Password reset mailbox: completed %s requests', count)
    except Timeout:
        return
    except Exception as exc:
        # Never log server responses, raw messages, addresses, tokens or credentials.
        logger.warning('Password reset mailbox deferred (%s)', type(exc).__name__)
