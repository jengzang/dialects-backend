import base64
from email.message import EmailMessage
from email.policy import SMTP

import dkim
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.service.auth.password_reset_mail import authenticated_request, MailVerificationTemporaryError


@pytest.fixture(scope='module')
def signing_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.PKCS1)
    return private, b'v=DKIM1; k=rsa; p=' + base64.b64encode(public)


def mail(signing_key, *, domain=b'gmail.com', sender='owner@gmail.com', body=None, length=False):
    msg = EmailMessage(policy=SMTP)
    msg['From'] = sender
    msg['To'] = '2639548777@qq.com'
    msg['Subject'] = 'Password reset'
    msg.set_content(body or 'RESET-REQUEST: ' + 'a' * 43)
    raw = msg.as_bytes()
    signature = dkim.sign(raw, b'test', domain, signing_key[0],
                          include_headers=[b'from', b'to', b'subject'], length=length)
    return signature + raw


def test_signed_request_is_independently_verified(signing_key):
    raw = mail(signing_key)
    assert authenticated_request(raw, dnsfunc=lambda *a, **kw: signing_key[1]) == ('owner@gmail.com', 'a' * 43)


@pytest.mark.parametrize('kind', ['unsigned', 'tampered', 'wrong_domain', 'partial_body', 'multiple_from', 'multiple_tokens'])
def test_forged_or_ambiguous_mail_is_rejected(signing_key, kind):
    raw = mail(signing_key)
    if kind == 'unsigned':
        raw = raw[raw.index(b'From:'):]
        raw = b'Authentication-Results: mx.qq.com; dkim=pass; dmarc=pass\r\n' + raw
    elif kind == 'tampered':
        raw = raw.replace(b'a' * 43, b'b' * 43)
    elif kind == 'wrong_domain':
        raw = mail(signing_key, domain=b'attacker.com')
    elif kind == 'partial_body':
        raw = mail(signing_key, length=True)
    elif kind == 'multiple_from':
        raw += b'\r\n'
        raw = b'From: attacker@gmail.com\r\n' + raw
    else:
        raw = mail(signing_key, body='RESET-REQUEST: ' + 'a' * 43 + '\nRESET-REQUEST: ' + 'b' * 43)
    assert authenticated_request(raw, dnsfunc=lambda *a, **kw: signing_key[1]) is None


def test_unknown_dns_or_oversized_mail_does_not_authorize_reset(signing_key):
    assert authenticated_request(mail(signing_key), dnsfunc=lambda *a, **kw: None) is None
    assert authenticated_request(b'x' * (256 * 1024 + 1)) is None


def test_dns_timeout_can_be_retried(signing_key):
    def unavailable(*args, **kwargs):
        raise dkim.DnsTimeoutError('temporary DNS failure')
    with pytest.raises(MailVerificationTemporaryError):
        authenticated_request(mail(signing_key), dnsfunc=unavailable)


def test_malformed_signature_cannot_poison_the_mailbox(signing_key):
    raw = mail(signing_key)
    unsigned = raw[raw.index(b'From:'):]
    assert authenticated_request(b'DKIM-Signature: bad-signature\r\n' + unsigned) is None
