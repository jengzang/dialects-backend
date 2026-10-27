"""Read-only warmup audit; optional explicit disposable Redis test instance.

Default in-memory substitute excludes network/cleanup I/O; --redis-url measures them.
Growth databases are disposable fixtures, never a production query strategy.
"""
import argparse
import asyncio
import cProfile
import json
import hashlib
import subprocess
import uuid
from types import ModuleType
from pathlib import Path
import resource
import sqlite3
import statistics
import sys
import tempfile
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.service.vocabulary import cache as cache_module, cache_warmup, query
from scripts.benchmark_vocabulary_entries import growth_fixture, readonly


class MemoryClient:
    """Only the Redis operations reached by this controlled serial benchmark."""
    def __init__(self):
        self.values = {}
    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True
    def get(self, key):
        return self.values.get(key)
    def delete(self, key):
        return self.values.pop(key, None) is not None
    def pipeline(self):
        client = self
        class Pipeline:
            def __init__(self): self.keys = []
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def exists(self, key): self.keys.append(key)
            def execute(self): return [key in client.values for key in self.keys]
        return Pipeline()
    def eval(self, script, numkeys, *args):
        keys, values = args[:numkeys], args[numkeys:]
        if script == cache_module._READ:
            return self.get(keys[0])
        if script == cache_module._WRITE:
            assert values[3] == 'default', 'Only permanent warmup keys are benchmarked'
            self.values[keys[1]] = values[2]
            return 1
        if script == cache_module._UNLOCK:
            if self.get(keys[0]) == values[0]:
                del self.values[keys[0]]
                return 1
            return 0
        if script == cache_module._RENEW:
            return int(self.get(keys[0]) == values[0])
        raise AssertionError('unexpected Redis command')


class OfflineCache(cache_module.VocabularyCache):
    def __init__(self, path):
        super().__init__(MemoryClient(), path, namespace='offline-warmup-benchmark')
        self.revision = {'entries': 'entries-1', 'locations': 'locations-1'}
    def state(self):
        return dict(self.revision)
    def cleanup(self):
        # Do not pretend dictionary iteration measures Redis SCAN/EVAL cost.
        pass


CACHE_CLASS = cache_module.VocabularyCache
REDIS_CLIENT = None
CREATED_CACHES = []


def new_cache(path):
    if REDIS_CLIENT is None:
        return OfflineCache(path)
    cache = CACHE_CLASS(REDIS_CLIENT, path, namespace='vocabulary-warmup-audit-'+uuid.uuid4().hex)
    CREATED_CACHES.append(cache)
    return cache


def load_baseline(ref):
    global cache_warmup, CACHE_CLASS
    for name in ['cache', 'cache_warmup']:
        source = subprocess.check_output(['git', 'show', f'{ref}:app/service/vocabulary/{name}.py'], text=True, cwd=ROOT)
        module = ModuleType('app.service.vocabulary._audit_'+name)
        module.__package__ = 'app.service.vocabulary'
        sys.modules[module.__name__] = module
        exec(compile(source, ref+':'+name, 'exec'), module.__dict__)
        if name == 'cache':
            CACHE_CLASS = module.VocabularyCache
        else:
            cache_warmup = module


def factory_for(path):
    engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(
        path.resolve().as_uri() + '?mode=ro', uri=True, check_same_thread=False))
    return engine, sessionmaker(bind=engine)


async def warm_cases(path, factory, rounds):
    results = []
    original = cache_warmup._load
    calls = []
    def measured(*args):
        start = time.perf_counter()
        value = original(*args)
        calls.append({'kind': args[1], 'params': args[2], 'ms': (time.perf_counter()-start)*1000})
        return value
    cache_warmup._load = measured
    try:
        for scenario in ['cold', 'ready', 'missing-map', 'locations-changed']:
            samples, call_samples, digests = [], [], []
            for _ in range(rounds):
                cache = new_cache(path)
                if scenario != 'cold':
                    assert await cache_warmup.warm_once(cache, factory, pause=0)
                if scenario == 'missing-map':
                    cache.client.delete(cache.key('map-points', {}))
                elif scenario == 'locations-changed':
                    if isinstance(cache, OfflineCache):
                        cache.revision['locations'] = 'locations-2'
                    else:
                        cache.invalidate('locations')
                calls.clear()
                start = time.perf_counter()
                assert await cache_warmup.warm_once(cache, factory)
                samples.append((time.perf_counter()-start)*1000)
                call_samples.append(list(calls))
                values = [cache.read(cache.key(k, p)) for k, p in cache_module.DEFAULTS]
                assert all(value is not None for value in values)
                digests.append(hashlib.sha256(cache_module.encoded(values).encode()).hexdigest())
            results.append(dict(scenario=scenario, median_ms=statistics.median(samples),
                                samples_ms=samples, load_calls=call_samples, payload_sha256=digests))
    finally:
        cache_warmup._load = original
    return results


async def interference(path, factory, rounds):
    from app.service.vocabulary.resources import run_bounded
    original = cache_warmup._load
    baseline, concurrent, loop_delays = [], [], []
    async def probe():
        def operation():
            with factory() as session:
                return query.query_vocabulary_items(session=session, q='什么')
        start = time.perf_counter()
        result = await run_bounded(path, operation)
        return (time.perf_counter()-start)*1000, result.total
    for _ in range(rounds):
        elapsed, expected = await probe()
        baseline.append(elapsed)
    loop = asyncio.get_running_loop()
    for _ in range(rounds):
        started = asyncio.Event()
        def measured(*args):
            if args[1] == 'standard-words':
                loop.call_soon_threadsafe(started.set)
            return original(*args)
        cache_warmup._load = measured
        task = asyncio.create_task(cache_warmup.warm_once(new_cache(path), factory))
        delays = []
        async def ticker():
            while not task.done():
                start = time.perf_counter()
                await asyncio.sleep(.005)
                delays.append(max(0, (time.perf_counter()-start)*1000-5))
        tick = asyncio.create_task(ticker())
        try:
            done, _ = await asyncio.wait([task, asyncio.create_task(started.wait())], return_when=asyncio.FIRST_COMPLETED)
            assert started.is_set(), 'warmup failed before standard-word stage'
            elapsed, total = await probe()
            assert total == expected
            concurrent.append(elapsed)
            assert await task
            await tick
            loop_delays.append(max(delays, default=0))
        finally:
            cache_warmup._load = original
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if not tick.done():
                tick.cancel()
                await asyncio.gather(tick, return_exceptions=True)
    return dict(probe='default-fields q=什么, one first-page service call; no HTTP/Redis',
                baseline_samples_ms=baseline, during_standard_words_samples_ms=concurrent,
                baseline_median_ms=statistics.median(baseline), concurrent_median_ms=statistics.median(concurrent),
                warmup_max_event_loop_delay_samples_ms=loop_delays)


def run(path, args):
    engine, factory = factory_for(path)
    try:
        with readonly(path) as conn:
            stats = dict(entries=conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0],
                         spellings=conn.execute('SELECT COUNT(DISTINCT standard_word) FROM vocabulary_entries').fetchone()[0],
                         location_names=conn.execute('SELECT COUNT(DISTINCT location_name) FROM vocabulary_entries').fetchone()[0])
        if args.interference:
            return dict(stats=stats, interference=asyncio.run(interference(path, factory, args.rounds)))
        if args.resource:
            tracemalloc.start()
            start = resource.getrusage(resource.RUSAGE_SELF)
            assert asyncio.run(cache_warmup.warm_once(new_cache(path), factory))
            end = resource.getrusage(resource.RUSAGE_SELF)
            peak = tracemalloc.get_traced_memory()[1]/1024**2
            tracemalloc.stop()
            rss = end.ru_maxrss / (1024**2 if sys.platform == 'darwin' else 1024)
            return dict(stats=stats, python_peak_mib=peak, process_lifetime_peak_rss_mib=rss,
                        query_user_cpu_s=end.ru_utime-start.ru_utime, query_system_cpu_s=end.ru_stime-start.ru_stime)
        stages = []
        for kind, params in [*cache_module.DEFAULTS[:5], cache_module.DEFAULTS[6]]:
            samples, encoding = [], []
            for iteration in range(args.rounds+1):
                start = time.perf_counter(); value = cache_warmup._load(factory, kind, params)
                elapsed = (time.perf_counter()-start)*1000
                start = time.perf_counter(); payload = cache_module.encoded(value)
                encode_ms = (time.perf_counter()-start)*1000
                if iteration:
                    samples.append(elapsed); encoding.append(encode_ms)
            stages.append(dict(kind=kind, params=params, load_ms=statistics.median(samples),
                               encoding_ms=statistics.median(encoding), utf8_bytes=len(payload.encode()),
                               load_samples=samples, encoding_samples=encoding))
        if args.profile:
            profiler = cProfile.Profile()
            profiler.runcall(cache_warmup._load, factory, 'standard-words', {'limit': 1000})
            profiler.dump_stats(str(args.profile))
        # Unlimited comparison is separate: prewarm itself still respects existing limits.
        with factory() as session:
            limited = query.query_vocabulary_standard_words(session=session, limit=1000)
            full = query.query_vocabulary_standard_words(session=session, limit=None)
            assert limited.total == full.total == len(full.standard_words)
            assert limited.standard_words == full.standard_words[:1000]
            full_groups = full.total
            del full, limited
        return dict(stats=stats, stages=stages, full_standard_word_groups=full_groups,
                    orchestration=asyncio.run(warm_cases(path, factory, args.rounds)))
    finally:
        engine.dispose()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scale', type=int, default=1)
    p.add_argument('--redis-url', help='Explicit disposable test Redis only; benchmark namespaces removed on exit')
    p.add_argument('--baseline', help='Load cache/warmup code from this git ref; service SQL stays current')
    p.add_argument('--distinct', action='store_true')
    p.add_argument('--rounds', type=int, default=5)
    p.add_argument('--resource', action='store_true')
    p.add_argument('--interference', action='store_true')
    p.add_argument('--pause-only-after-query', action='store_true', help='Isolated scheduling candidate; does not change application source')
    p.add_argument('--profile', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.scale < 1 or args.rounds < 1 or (args.distinct and args.scale < 2):
        p.error('scale/rounds must be positive; distinct needs scale>=2')
    if args.baseline:
        load_baseline(args.baseline)
    if args.pause_only_after_query:
        if not args.baseline:
            p.error('--pause-only-after-query requires a pre-optimization --baseline, e.g. 820e177')
        source_text = subprocess.check_output(['git', 'show', f'{args.baseline}:app/service/vocabulary/cache_warmup.py'], text=True, cwd=ROOT)
        for fragment in ['            async def load():', '                return await run_bounded(', '            await asyncio.sleep(pause)']:
            assert source_text.count(fragment) == 1, 'Warmup source changed; review candidate transformation'
        source_text = source_text.replace('            async def load():', '            queried = False\n            async def load():\n                nonlocal queried')
        source_text = source_text.replace('                return await run_bounded(', '                queried = True\n                return await run_bounded(')
        source_text = source_text.replace('            await asyncio.sleep(pause)', '            if queried:\n                await asyncio.sleep(pause)')
        exec(compile(source_text, '<isolated-pause-candidate>', 'exec'), cache_warmup.__dict__)
    global REDIS_CLIENT
    if args.redis_url:
        import redis
        REDIS_CLIENT = redis.Redis.from_url(args.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=5)
        REDIS_CLIENT.ping()
    source = ROOT/'data/vocabulary.db'
    report = dict(note='Offline Redis substitute: real warm_once, queries, JSON, pauses and admission; excludes Redis network, SCAN/EVAL cleanup cost, TTL/eviction/concurrency semantics. Sequential local measurements, not production capacity.',
                  real_redis=bool(args.redis_url), baseline=args.baseline, sqlite=sqlite3.sqlite_version, scale=args.scale, distinct=args.distinct,
                  rounds=args.rounds, resource=args.resource, pause_only_after_query=args.pause_only_after_query, interference=args.interference)
    if args.scale == 1:
        report.update(run(source, args))
    else:
        with tempfile.TemporaryDirectory(prefix='vocabulary-warmup-audit-') as directory:
            target = Path(directory)/'growth.db'
            growth_fixture(source, target, args.scale)
            if args.distinct:
                with readonly(source) as original:
                    stride = original.execute('SELECT MAX(user_id)+1 FROM (SELECT user_id FROM vocabulary_entries UNION ALL SELECT user_id FROM vocabulary_locations)').fetchone()[0]
                with sqlite3.connect(target) as conn:
                    for table in ['vocabulary_entries', 'vocabulary_locations']:
                        conn.execute(f"UPDATE {table} SET location_name=location_name||'·新增'||user_id WHERE user_id>=?", (stride,))
                    conn.execute("UPDATE vocabulary_entries SET standard_word=standard_word||'·新增'||user_id WHERE user_id>=?", (stride,))
            report.update(run(target, args))
    if REDIS_CLIENT is not None:
        report['note'] = 'Real supplied test Redis, real SQL/JSON/admission/pauses/cleanup; isolated disposable namespaces. Local sequential warm-page calls, not production CPU/RAM or disk-cold capacity.'
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        if REDIS_CLIENT is not None:
            for cache in CREATED_CACHES:
                batch = []
                for key in REDIS_CLIENT.scan_iter(match=cache.root+':*', count=32):
                    batch.append(key)
                    if len(batch) >= 32:
                        REDIS_CLIENT.unlink(*batch); batch.clear()
                if batch:
                    REDIS_CLIENT.unlink(*batch)
            REDIS_CLIENT.close()
