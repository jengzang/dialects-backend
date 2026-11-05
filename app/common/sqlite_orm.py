"""Shared SQLite ORM construction and process-local resource lifecycle.

Policies preserve existing settings. Engines remain separate per database/worker;
registration does not open connections or retain temporary engines permanently.
Schema creation and migrations belong to the calling database modules.
"""
import logging
from dataclasses import dataclass
from threading import Lock
from types import MappingProxyType
from weakref import WeakKeyDictionary

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SQLitePolicy:
    busy_timeout_ms: int = 5000
    foreign_keys: bool | None = True
    cache_kib: int | None = None
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30


POLICIES = MappingProxyType({
    'auth': SQLitePolicy(),
    'supplements': SQLitePolicy(),
    'logs': SQLitePolicy(foreign_keys=None, cache_kib=64000),
    'vocabulary': SQLitePolicy(busy_timeout_ms=10000),
})
_engines = WeakKeyDictionary()
_registry_lock = Lock()


def _configure_connection(connection, policy: SQLitePolicy, profile: str) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute(f'PRAGMA busy_timeout={policy.busy_timeout_ms}')
        try:
            cursor.execute('PRAGMA journal_mode=WAL')
        except Exception as exc:
            logger.warning('%s: WAL unavailable (%s), falling back to DELETE', profile, exc)
            cursor.execute('PRAGMA journal_mode=DELETE')
        cursor.execute('PRAGMA synchronous=NORMAL')
        if policy.foreign_keys is not None:
            cursor.execute(f'PRAGMA foreign_keys={int(policy.foreign_keys)}')
        if policy.cache_kib is not None:
            cursor.execute(f'PRAGMA cache_size=-{policy.cache_kib}')
    finally:
        cursor.close()


def make_session_factory(bind):
    """Create independent sessions using an existing engine/connection."""
    return sessionmaker(bind=bind, autocommit=False, autoflush=False)


def create_engine_and_session(profile: str, url):
    if profile not in POLICIES:
        raise ValueError(f'Unknown SQLite ORM profile: {profile}')
    parsed = make_url(url)
    if parsed.get_backend_name() != 'sqlite':
        raise ValueError('SQLite ORM manager only supports SQLite URLs')
    policy = POLICIES[profile]
    options = {}
    is_memory = (parsed.database in (None, '', ':memory:')
                 or parsed.query.get('mode') == 'memory'
                 or (parsed.database or '').startswith('file::memory:'))
    if not is_memory:
        options.update(poolclass=QueuePool, pool_size=policy.pool_size,
                       max_overflow=policy.max_overflow, pool_timeout=policy.pool_timeout)
    engine = create_engine(
        parsed, connect_args={'check_same_thread': False, 'timeout': policy.busy_timeout_ms / 1000},
        pool_pre_ping=True, **options,
    )
    # Capture policy/profile only: capturing engine here would keep it alive.
    event.listen(engine, 'connect', lambda conn, record: _configure_connection(conn, policy, profile))
    with _registry_lock:
        _engines[engine] = profile
    return engine, make_session_factory(engine)


def _snapshot():
    with _registry_lock:
        return list(_engines.items())


def pool_status() -> list[dict]:
    """Inspect existing pools without issuing SQL or opening connections."""
    result = []
    for engine, profile in _snapshot():
        pool = engine.pool
        item = {'profile': profile, 'pool_type': type(pool).__name__}
        if isinstance(pool, QueuePool):
            item.update(size=pool.size(), checked_out=pool.checkedout(),
                        checked_in=pool.checkedin(), overflow=pool.overflow())
        result.append(item)
    return result


def dispose_all_orm_engines() -> dict[str, int]:
    """Release idle handles after requests/background work have drained.

    SQLAlchemy does not forcibly close checked-out connections. Existing factories
    can reconnect if the application lifespan starts again in this process.
    """
    counts = {'disposed': 0, 'failed': 0}
    for engine, profile in _snapshot():
        try:
            engine.dispose()
            counts['disposed'] += 1
        except Exception:
            counts['failed'] += 1
            logger.exception('Failed disposing ORM engine: %s', profile)
    return counts
