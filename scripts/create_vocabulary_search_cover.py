"""One explicit, bounded SQLite index migration; stdlib only, never app startup.

Run with the application's Python/user and a live WAL database. Readers can
continue; SQLite writers may wait during this single transaction. No retries,
checkpoint, ANALYZE, VACUUM, app imports or persistent PRAGMA changes.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import resource
import signal
import sqlite3
import sys
import time

NAME = 'idx_vocabulary_entries_search_cover'
COLUMNS = ('standard_word', 'location_name', 'local_expression', 'user_id')


def available_mib():
    with open('/proc/meminfo') as stream:
        for line in stream:
            if line.startswith('MemAvailable:'):
                return int(line.split()[1]) / 1024
    raise RuntimeError('MemAvailable unavailable; refusing migration')


def cgroup_headroom_mib():
    for limit_path, usage_path in (
        ('/sys/fs/cgroup/memory/memory.limit_in_bytes', '/sys/fs/cgroup/memory/memory.usage_in_bytes'),
        ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory.current'),
    ):
        if os.path.exists(limit_path):
            limit = Path(limit_path).read_text().strip()
            if limit == 'max' or int(limit) >= 1 << 60:
                return None
            return (int(limit) - int(Path(usage_path).read_text())) / (1024 * 1024)
    return None


def index_ready(conn):
    indexes = conn.execute('PRAGMA main.index_list(vocabulary_entries)')
    row = next((row for row in indexes if row[1] == NAME), None)
    indexes.close()
    if row is None:
        return False
    columns = [(row[2], row[3], row[4]) for row in conn.execute(
        f'PRAGMA main.index_xinfo({NAME})') if row[5]]
    if row[2] or row[4] or columns != [(column, 0, 'BINARY') for column in COLUMNS]:
        raise RuntimeError('Existing named index has an incompatible definition')
    return True


def sizes(path):
    return {suffix or 'db': Path(str(path) + suffix).stat().st_size
            if Path(str(path) + suffix).exists() else 0 for suffix in ('', '-wal', '-shm')}


def migrate(path, max_seconds, require_watchdog=False, io_class='idle'):
    if not sys.platform.startswith('linux'):
        raise RuntimeError('Resource guards require Linux')
    path = path.resolve(strict=True)
    os.nice(19)
    # Process-local scheduling only; use the libc wrapper, not arch-specific syscall IDs.
    libc = ctypes.CDLL(None, use_errno=True)
    priority = (3 << 13) if io_class == 'idle' else (2 << 13) | 7
    priority_set = False
    if hasattr(libc, 'ioprio_set'):
        priority_set = libc.ioprio_set(1, 0, priority) == 0
    elif os.uname().machine in ('x86_64', 'aarch64'):
        syscall = 251 if os.uname().machine == 'x86_64' else 30
        priority_set = libc.syscall(syscall, 1, 0, priority) == 0
    if not priority_set:
        raise RuntimeError('Unable to set low I/O priority; refusing migration')
    # SQLite threads=0 below keeps one execution thread. Let the scheduler move
    # it to an idle CPU rather than forcing contention on CPU 0.
    resource.setrlimit(resource.RLIMIT_AS, (96 * 1024 * 1024, 96 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 65))
    before = sizes(path)
    free = os.statvfs(path.parent)
    if free.f_bavail * free.f_frsize < 512 * 1024 * 1024:
        raise RuntimeError('Less than 512 MiB free disk')
    initial_available = available_mib()
    if initial_available < 192:
        raise RuntimeError(f'Only {initial_available:.1f} MiB available; need 192 MiB to start')
    initial_headroom = cgroup_headroom_mib()
    if initial_headroom is not None and initial_headroom < 128:
        raise RuntimeError('Container memory headroom below 128 MiB')
    acknowledged = False
    def acknowledge(signum, frame):
        nonlocal acknowledged
        acknowledged = True
    if require_watchdog:
        signal.signal(signal.SIGUSR1, acknowledge)
    print(json.dumps({'status': 'starting', 'pid': os.getpid()}), flush=True)
    if require_watchdog:
        until = time.monotonic() + 2
        while not acknowledged and time.monotonic() < until:
            time.sleep(0.01)
        if not acknowledged:
            raise RuntimeError('Watchdog did not acknowledge PID; no DDL started')
    conn = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=0.1,
                           isolation_level=None)
    try:
        if conn.execute('PRAGMA journal_mode').fetchone()[0].lower() != 'wal':
            raise RuntimeError('Database is not WAL; refusing to change journal mode')
        if index_ready(conn):
            return {'status': 'already_exists', 'sizes': before}
        # Session-local settings. In particular, do not checkpoint the live WAL.
        for pragma in ('cache_size=-1024', 'mmap_size=0', 'temp_store=FILE',
                       'threads=0', 'wal_autocheckpoint=0', 'busy_timeout=100'):
            conn.execute('PRAGMA ' + pragma)
        started = time.monotonic()
        stopped = []
        last_check = started
        def progress():
            nonlocal last_check
            now = time.monotonic()
            if now - started >= max_seconds:
                stopped.append('execution deadline'); return 1
            if now - last_check >= 0.05:
                last_check = now
                try:
                    if available_mib() < 128:
                        stopped.append('available memory below 128 MiB'); return 1
                    headroom = cgroup_headroom_mib()
                    if headroom is not None and headroom < 64:
                        stopped.append('container headroom below 64 MiB'); return 1
                except OSError:
                    stopped.append('memory guard unavailable'); return 1
            return 0
        conn.set_progress_handler(progress, 10000)
        def expired(signum, frame):
            raise TimeoutError('Migration wall-clock guard expired')
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, max_seconds + 2)
        try:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute(f'CREATE INDEX {NAME} ON vocabulary_entries({",".join(COLUMNS)})')
            conn.execute('COMMIT')
        except BaseException as exc:
            conn.set_progress_handler(None, 0)
            if conn.in_transaction:
                conn.execute('ROLLBACK')
            raise RuntimeError(f'Migration stopped: {stopped or [str(exc)]}') from exc
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            conn.set_progress_handler(None, 0)
        elapsed = time.monotonic() - started
        if not index_ready(conn):
            raise RuntimeError('Index verification failed after commit')
        return {'status': 'created', 'elapsed_s': elapsed,
                'sizes_before': before, 'sizes_after': sizes(path),
                'rss_peak_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'available_mib_before': initial_available,
                'available_mib_after': available_mib(), 'nice': os.nice(0),
                'io_class': io_class, 'io_priority': None if io_class == 'idle' else 7,
                'cgroup_headroom_mib_before': initial_headroom,
                'cgroup_headroom_mib_after': cgroup_headroom_mib(),
                'max_seconds': max_seconds,
                'cache_kib': 1024, 'virtual_memory_cap_mib': 96}
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('--max-seconds', type=float, default=4.0)
    parser.add_argument('--require-watchdog', action='store_true')
    parser.add_argument('--watchdog-token', default='')
    parser.add_argument('--io-class', choices=('idle', 'best-effort'), default='idle')
    args = parser.parse_args()
    if args.require_watchdog and not args.watchdog_token:
        parser.error('require-watchdog also requires watchdog-token')
    if not 0 < args.max_seconds <= 180:
        parser.error('max-seconds must be >0 and <=180')
    try:
        print(json.dumps(migrate(args.database, args.max_seconds, args.require_watchdog, args.io_class)), flush=True)
    except Exception as exc:
        print(json.dumps({'status': 'stopped', 'error': str(exc)}), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
