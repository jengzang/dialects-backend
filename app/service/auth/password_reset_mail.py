"""Authenticate the original signed bytes, never mailbox-provided result headers."""
import re
from email import policy
from email.parser import BytesParser

import dkim
import dns.exception
import dns.resolver
from dkim.util import InvalidTagValueList, parse_tag_value

MAX_MAIL_BYTES = 256 * 1024
TOKEN_LINE = re.compile(r'^RESET-REQUEST:[ \t]*([A-Za-z0-9_-]{43})[ \t]*\r?$', re.MULTILINE)


class MailVerificationTemporaryError(RuntimeError):
    pass


def _dns_key(name, timeout=5):
    try:
        answer = dns.resolver.resolve(name.decode('ascii'), 'TXT', lifetime=timeout, search=False)
        return b''.join(answer[0].strings)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return None
    except dns.exception.DNSException as exc:
        raise MailVerificationTemporaryError('Mail signature DNS temporarily unavailable') from exc


def authenticated_request(raw, *, dnsfunc=None):
    if len(raw) > MAX_MAIL_BYTES:
        return None
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        if message.defects or len(message.get_all('From', [])) != 1:
            return None
        sender_header = message['From']
        if sender_header.defects or len(sender_header.addresses) != 1:
            return None
        sender = sender_header.addresses[0].addr_spec
        local, domain = sender.rsplit('@', 1)
        if not local or not domain or not sender.isascii():
            return None
        body = message.get_body(preferencelist=('plain',))
        if body is None:
            return None
        tokens = TOKEN_LINE.findall(body.get_content())
        if len(tokens) != 1:
            return None
        verifier = dkim.DKIM(raw, minkey=1024, timeout=5)
        signatures = [value for name, value in verifier.headers if name.lower() == b'dkim-signature']
        for index, signature in enumerate(signatures[:5]):
            tags = parse_tag_value(signature)
            # Exact alignment intentionally excludes ambiguous delegated/subdomain senders.
            if tags.get(b'd', b'').decode('ascii').lower() != domain.lower() or b'l' in tags:
                continue
            if b'from' not in [name.strip().lower() for name in tags.get(b'h', b'').split(b':')]:
                continue
            def lookup(name, timeout=5):
                try:
                    return (dnsfunc or _dns_key)(name, timeout=timeout)
                except dkim.DnsTimeoutError as exc:
                    raise MailVerificationTemporaryError('Mail signature DNS temporarily unavailable') from exc
            if verifier.verify(idx=index, dnsfunc=lookup):
                return sender, tokens[0]
    except (ValueError, TypeError, UnicodeError, LookupError, InvalidTagValueList, dkim.DKIMException):
        return None
    return None
