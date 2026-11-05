"""Six bounded, versioned Redis results. Call only from an existing worker thread."""
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import tempfile
import threading

log = logging.getLogger(__name__)
PREFIX = "fixed_default:v1:"
SLOTS = frozenset((
    "yubao:vocabulary_all", "yubao:grammar_all",
    "sql:query_stored_count", "sql:dialects_count",
    "villages:gd:ngrams", "villages:gd:tables",
))
REVISIONS = {slot: 1 for slot in SLOTS}
_client = None
_client_lock = threading.Lock()
MAX_PAYLOAD_BYTES = 1024 * 1024
_MISSING = object()


def key(slot):
    if slot not in SLOTS:
        raise ValueError("Unknown fixed default cache slot")
    return PREFIX + slot


def version(path, slot=None):
    """Conservative file generation; never scan/hash database contents."""
    path = os.path.realpath(path)
    stamps = []
    try:
        for name in (path, path + "-wal"):
            try:
                st = os.stat(name)
                stamps.append([st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns])
            except FileNotFoundError:
                if name == path:
                    return None
                stamps.append(None)
    except OSError:
        return None
    return [REVISIONS[slot] if slot is not None else 1, path, stamps]


def client_or_default(client=None):
    if client is not None:
        return client
    from app import redis_client as configured
    if configured._RUN_TYPE != "WEB":
        return configured.sync_redis_client
    global _client
    with _client_lock:
        if _client is None:
            from redis import Redis, ConnectionPool
            from redis.backoff import NoBackoff
            from redis.retry import Retry
            original = configured.sync_redis_client.connection_pool
            options = dict(original.connection_kwargs)
            options.update(socket_timeout=0.2, socket_connect_timeout=0.2,
                           retry=Retry(NoBackoff(), 0), retry_on_timeout=False, retry_on_error=[])
            _client = Redis(connection_pool=ConnectionPool(
                connection_class=original.connection_class, max_connections=2, **options))
        return _client


def close_client():
    global _client
    with _client_lock:
        if _client is not None:
            _client.connection_pool.disconnect()
            _client = None


@contextmanager
def publication_lock(name="build"):
    """Nonblocking host-wide lock, also held by the single startup warmer."""
    if name not in ("build", "warmup"):
        raise ValueError("Unknown fixed cache lock")
    fd = None
    acquired = False
    try:
        import fcntl
        root = Path(os.environ.get("FIXED_DEFAULT_LOCK_DIR",
                        str(Path(tempfile.gettempdir()) / "dialects-fixed-default-cache")))
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(root / (name + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquired = True
    except (OSError, ImportError):
        pass
    try:
        yield acquired
    finally:
        if fd is not None:
            os.close(fd)


def lookup(slot, path, client):
    cache_key = key(slot)
    before = version(path, slot)
    if before is None:
        return _MISSING
    raw = client.get(cache_key)
    if raw is None:
        return _MISSING
    try:
        if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > MAX_PAYLOAD_BYTES + 4096:
            return _MISSING
        entry = json.loads(raw)
        if (isinstance(entry, dict) and entry.get("version") == before
                and "payload" in entry and version(path, slot) == before):
            return entry["payload"]
    except (ValueError, TypeError, UnicodeError):
        pass
    return _MISSING


def _encode(payload, stamp):
    # iterencode bounds serialized copies; the existing response itself is not truncated.
    pieces, size = [], 0
    for part in json.JSONEncoder(ensure_ascii=False, separators=(",", ":"), allow_nan=False).iterencode(payload):
        chunk = part.encode("utf-8")
        size += len(chunk)
        if size > MAX_PAYLOAD_BYTES:
            return None
        pieces.append(part)
    return '{"version":' + json.dumps(stamp, separators=(",", ":")) + ',"payload":' + ''.join(pieces) + '}'


def publish(slot, path, stamp, result, client):
    if stamp is None or version(path, slot) != stamp:
        return
    payload = _encode(result, stamp)
    if payload is not None and version(path, slot) == stamp:
        client.set(key(slot), payload)  # Deliberately no TTL. Replace the same slot.


def call(slot, path, loader, *, client=None):
    """Misses run normally. They never wait for startup warmup or another request."""
    key(slot)
    client = client_or_default(client)
    healthy = True
    try:
        hit = lookup(slot, path, client)
        if hit is not _MISSING:
            return hit
    except Exception:
        healthy = False
    stamp = version(path, slot)
    result = loader()
    if healthy:
        try:
            with publication_lock() as acquired:
                if acquired:
                    publish(slot, path, stamp, result, client)
        except Exception:
            log.debug("Fixed cache publication skipped", exc_info=True)
    return result
