"""Host-side watchdog for one explicitly authorized container index migration.

Reads only host counters and newly appended Nginx lines. Starts exactly one
migration; no automatic retries or API probes. May signal only the PID reported
by that migration. Always verify the database separately after an abnormal exit.
Compatible with the production host's Python 3.6; source can be streamed over SSH.
"""
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time
import uuid


def snapshot():
    with open('/proc/meminfo') as stream:
        mem = {line.split(':')[0]: int(line.split()[1]) for line in stream
               if line.startswith(('MemAvailable:', 'SwapTotal:', 'SwapFree:'))}
    return {'available_mib': mem['MemAvailable'] / 1024,
            'swap_used_mib': (mem['SwapTotal'] - mem['SwapFree']) / 1024,
            'load1': os.getloadavg()[0]}


def supervise(source, container, database, nginx_log, max_seconds=4.0, io_class='idle'):
    if not 0 < max_seconds <= 180:
        raise ValueError('Migration budget must be >0 and <=180 seconds')
    if io_class not in ('idle', 'best-effort'):
        raise ValueError('Unsupported I/O class')
    os.nice(19)
    baseline = snapshot()
    if baseline['available_mib'] < 192:
        return {'status': 'not_started', 'reason': 'available memory below 192 MiB',
                'baseline': baseline}
    # Do not hold/scan old logs; watch only bounded new data during this operation.
    log = open(nginx_log, 'rb')
    log.seek(0, os.SEEK_END)
    token = uuid.uuid4().hex
    process = subprocess.Popen(['docker', 'exec', '-i', container, 'python', '-', database,
                                '--require-watchdog', '--watchdog-token', token,
                                '--max-seconds', str(max_seconds), '--io-class', io_class],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    started = time.monotonic()
    process.stdin.write(source.encode('utf-8'))
    process.stdin.close()
    pid = None
    identity = None
    events, samples = [], []
    summary = {'minimum_available_mib': baseline['available_mib'],
               'maximum_swap_used_mib': baseline['swap_used_mib'],
               'maximum_target_rss_kib': 0, 'maximum_target_cpu_s': 0}
    reason = None
    interrupted = killed = False
    interrupt_time = None
    def ticks(host_pid):
        try:
            with open('/proc/%s/stat' % host_pid) as stream:
                return stream.read().rsplit(')', 1)[1].split()[19]
        except (OSError, IndexError):
            return None
    def locate(container_pid):
        # Identify our exact invocation independently of Docker signal forwarding.
        # The nonce cannot match another request/maintenance process.
        with os.scandir('/proc') as entries:
            for number, entry in enumerate(entries):
                if number >= 4096:
                    raise RuntimeError('Too many processes for bounded PID discovery')
                if not entry.name.isdigit():
                    continue
                try:
                    with open(entry.path + '/cmdline', 'rb') as stream:
                        args = stream.read(4096).split(b'\0')
                    if (token.encode() not in args or database.encode() not in args
                            or not os.path.basename(args[0]).startswith(b'python')):
                        continue
                    with open(entry.path + '/status') as stream:
                        namespace = next(line for line in stream if line.startswith('NSpid:'))
                    if int(namespace.split()[-1]) != container_pid:
                        continue
                    host_pid = int(entry.name)
                    start_ticks = ticks(host_pid)
                    if start_ticks is not None:
                        return host_pid, start_ticks
                except (OSError, StopIteration, ValueError):
                    continue
        raise RuntimeError('Cannot identify the exact migration process; no DDL acknowledged')
    def alive():
        return identity is not None and ticks(identity[0]) == identity[1]
    def stop(sig):
        if alive():
            try:
                os.kill(identity[0], getattr(signal, 'SIG' + sig))
                events.append({'signal': sig, 'host_pid': identity[0], 'sent': True})
                return True
            except OSError as exc:
                events.append({'signal': sig, 'sent': False, 'error': str(exc)})
        return False
    try:
        while process.poll() is None:
            ready, _, _ = select.select([process.stdout], [], [], 0.1)
            if ready:
                line = process.stdout.readline(8192).decode('utf-8', errors='replace').strip()
                if line:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        event = {'output': line[:1024]}
                    if event.get('status') == 'starting':
                        pid = int(event['pid'])
                        if pid <= 1:
                            raise RuntimeError('Invalid migration PID')
                        identity = locate(pid)
                        if not stop('USR1'):
                            raise RuntimeError('Could not acknowledge the migration process')
                    if len(events) < 16:
                        events.append(event)
            now = time.monotonic()
            state = snapshot()
            state['elapsed_s'] = now - started
            if alive():
                try:
                    with open('/proc/%s/stat' % identity[0]) as stream:
                        stat = stream.read().rsplit(')', 1)[1].split()
                    state['target_cpu_s'] = (int(stat[11]) + int(stat[12])) / os.sysconf('SC_CLK_TCK')
                    with open('/proc/%s/status' % identity[0]) as stream:
                        rss = next(line for line in stream if line.startswith('VmRSS:'))
                    state['target_rss_kib'] = int(rss.split()[1])
                except (OSError, StopIteration, ValueError):
                    pass
            if len(samples) < 80:
                samples.append(state)
            summary['minimum_available_mib'] = min(summary['minimum_available_mib'], state['available_mib'])
            summary['maximum_swap_used_mib'] = max(summary['maximum_swap_used_mib'], state['swap_used_mib'])
            summary['maximum_target_rss_kib'] = max(summary['maximum_target_rss_kib'], state.get('target_rss_kib', 0))
            summary['maximum_target_cpu_s'] = max(summary['maximum_target_cpu_s'], state.get('target_cpu_s', 0))
            new_log = log.read(65536)
            if state['available_mib'] < 128:
                reason = reason or 'available memory below 128 MiB'
            if state['swap_used_mib'] - baseline['swap_used_mib'] > 4:
                reason = reason or 'swap usage increased by more than 4 MiB'
            if re.search(rb'"(?:POST|PUT|PATCH|DELETE) /api/vocabulary/', new_log):
                reason = reason or 'vocabulary write request observed'
            if now - started > max_seconds + 1:
                reason = reason or 'external watchdog deadline'
            if reason and not interrupted:
                interrupted = True
                interrupt_time = now
                if pid is None:
                    process.kill()  # No acknowledged PID: DDL cannot have started.
                else:
                    stop('INT')
            if interrupted and not killed and now - interrupt_time > 1:
                killed = True
                stop('KILL')
            if now - started > max_seconds + 4:
                process.kill()
                break
        process.wait(timeout=1)
        if process.returncode != 0 and alive():
            stop('INT')
            until = time.monotonic() + 1
            while alive() and time.monotonic() < until:
                time.sleep(0.05)
            if alive():
                stop('KILL')
        # Drain the finite final status, including immediate preflight failures.
        remaining = process.stdout.read(16384).decode('utf-8', errors='replace')
        for line in remaining.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                event = {'output': line[:1024]}
            if len(events) < 16:
                events.append(event)
        return {'exit_code': process.returncode, 'reason': reason,
                'interrupted': interrupted, 'killed': killed,
                'elapsed_s': time.monotonic() - started,
                'baseline': baseline, 'final': snapshot(),
                'samples': samples, 'summary': summary, 'events': events}
    finally:
        log.close()
        if alive():
            stop('INT')
            until = time.monotonic() + 1
            while alive() and time.monotonic() < until:
                time.sleep(0.05)
            if alive():
                stop('KILL')
        if process.poll() is None:
            process.kill()
            process.wait(timeout=1)


if __name__ == '__main__':
    source_path, container, database, nginx_log = sys.argv[1:]
    print(json.dumps(supervise(Path(source_path).read_text(), container, database, nginx_log)))
