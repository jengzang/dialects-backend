"""Measure committed vocabulary queries in isolated local processes.

Use --prepare on the host, then --batch inside a resource-limited container.
No server access. Input DBs are read-only; --prepare writes only offline copies.
Time, RSS and Python allocation runs are separate. Results are verified outside
the measured region; entries additionally compare every matched row in ID order.
"""
import argparse
from dataclasses import fields, is_dataclass
import gc
import hashlib
import json
from pathlib import Path
import platform
import re
import resource
import sqlite3
import statistics
import subprocess
import sys
import time
import tracemalloc
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def load(path):
    module = ModuleType('_vocabulary_release')
    sys.modules[module.__name__] = module
    exec(compile(path.read_text(), str(path), 'exec'), module.__dict__)
    return module


def digest(value):
    h = hashlib.sha256()
    def visit(item):
        if is_dataclass(item):
            h.update(b'{')
            for field in fields(item):
                h.update(field.name.encode())
                visit(getattr(item, field.name))
            h.update(b'}')
        elif isinstance(item, (list, tuple)):
            h.update(b'[')
            for child in item:
                visit(child)
            h.update(b']')
        else:
            h.update(repr(item).encode())
            h.update(b'\0')
    visit(value)
    return h.hexdigest()


def proc_io():
    path = Path('/proc/self/io')
    return dict(line.split(': ', 1) for line in path.read_text().splitlines()) if path.exists() else {}


def rss_kib():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / 1024 if sys.platform == 'darwin' else rss


def child(args):
    module = load(args.source)
    job = json.loads(args.job)
    conn = readonly(args.db)
    session = SimpleNamespace(connection=lambda: SimpleNamespace(connection=conn))
    query = getattr(module, 'query_vocabulary_' + job['endpoint'])
    params = dict(job['params'])
    if job.get('cached_count'):
        total = query(session=session, **params).total
        params['_count_loader'] = lambda *_: total
    gc.collect()
    pre_query_peak_rss, before_io = rss_kib(), proc_io()
    if args.mode == 'heap':
        tracemalloc.start()
    samples = []
    for _ in range(args.rounds if args.mode == 'time' else 1):
        start = time.perf_counter()
        result = query(session=session, **params)
        samples.append((time.perf_counter() - start) * 1000)
        if args.mode == 'time':
            del result
            gc.collect()
    peak_heap = tracemalloc.get_traced_memory()[1] if args.mode == 'heap' else None
    if args.mode == 'heap':
        tracemalloc.stop()
    peak_rss, after_io = rss_kib(), proc_io()
    # Capture actual SQL and response equality separately, after measurement.
    statements = []
    conn.set_trace_callback(statements.append)
    value = query(session=session, **params)
    conn.set_trace_callback(None)
    signature = digest(value)
    full_rows = None
    if job['endpoint'] == 'items':
        page = [s for s in statements if s.startswith('SELECT') and not s.startswith('SELECT COUNT(*)')]
        if page:
            sql = re.sub(r'LIMIT \d+ OFFSET \d+', 'LIMIT -1 OFFSET 0', page[-1], count=1)
            count, h = 0, hashlib.sha256()
            for row in conn.execute(sql):
                count += 1
                h.update(repr(row).encode())
            full_rows = [count, h.hexdigest()]
            assert count == value.total, (job, count, value.total)
        else:
            assert value.total == 0 or job['params'].get('page', 1) > 1
            full_rows = [0, hashlib.sha256().hexdigest()] if value.total == 0 else None
    print(json.dumps(dict(median_ms=statistics.median(samples), samples_ms=samples,
        first_ms=samples[0], peak_rss_kib=peak_rss, pre_query_peak_rss_kib=pre_query_peak_rss,
        python_peak_bytes=peak_heap, signature=signature, full_rows=full_rows,
        total=value.total if hasattr(value, 'total') else value.total_entries,
        returned=len(value.items) if hasattr(value, 'items') else len(value.standard_words)
                 if hasattr(value, 'standard_words') else len(value.points),
        query_process_io_delta={k: int(after_io[k])-int(before_io[k]) for k in after_io},
        sql=[s for s in statements if s.startswith(('SELECT', 'WITH'))]), ensure_ascii=False))


def prepare(args):
    args.work.mkdir(parents=True, exist_ok=True)
    baseline = subprocess.check_output(['git', 'show', args.baseline + ':app/service/vocabulary/query.py'],
                                       cwd=ROOT, text=True)
    (args.work / 'before.py').write_text(baseline)
    (args.work / 'after.py').write_text((ROOT / 'app/service/vocabulary/query.py').read_text())
    growth = ROOT / 'outputs/vocabulary-local-20261101/scale5.sqlite'
    # Immutable offline inputs avoid needing WAL shared-memory creation on a
    # read-only repository mount when another local connection closes its WAL.
    for source, name in ((ROOT/'data/vocabulary.db','current.db'), (growth,'row-growth.db')):
        target = args.work/name
        if not target.exists():
            with readonly(source) as src, sqlite3.connect(target) as dest:
                src.backup(dest)
        with sqlite3.connect(target) as dest:
            dest.execute('PRAGMA journal_mode=DELETE')
    target = args.work / 'spelling-growth.db'
    if not target.exists():
        with readonly(growth) as src, sqlite3.connect(target) as dest, readonly(ROOT / 'data/vocabulary.db') as original:
            src.backup(dest)
            stride = original.execute('SELECT MAX(user_id)+1 FROM (SELECT user_id FROM vocabulary_entries '
                                      'UNION ALL SELECT user_id FROM vocabulary_locations)').fetchone()[0]
            dest.execute("UPDATE vocabulary_entries SET standard_word='g'||CAST(user_id / ? AS INTEGER)||':'||standard_word WHERE standard_word<>''", (stride,))
    high_hit = args.work / 'high-hit.db'
    if not high_hit.exists():
        with readonly(ROOT / 'data/vocabulary.db') as src, sqlite3.connect(high_hit) as dest:
            src.backup(dest)
            dest.execute("UPDATE vocabulary_entries SET standard_word='共同'||standard_word, local_expression='共同'||local_expression WHERE standard_word<>''")
    for target in (args.work/'spelling-growth.db', high_hit):
        with sqlite3.connect(target) as dest:
            dest.execute('PRAGMA journal_mode=DELETE')
    cases = []
    def add(name, endpoint, params, datasets=('current', 'growth'), modes=('time','rss')):
        cases.append(dict(name=name, endpoint=endpoint, params=params, datasets=list(datasets), modes=list(modes)))
    for fields_name, search_fields in [('definition',['definition']), ('headword',['headword']),
                                       ('both',['definition','headword'])]:
        for scope, locations in [('global',[]), ('small',['天柱竹林']), ('large',['廣州白話'])]:
            add(f'entries-{fields_name}-{scope}-spider', 'items',
                dict(q='蜘蛛',search_fields=search_fields,locations=locations))
        add(f'entries-{fields_name}-small-none', 'items',
            dict(q='不存在词8f0b',search_fields=search_fields,locations=['天柱竹林']))
        add(f'map-{fields_name}-global-spider','map_points',dict(q='蜘蛛', search_fields=search_fields))
        add(f'map-{fields_name}-global-skin','map_points',dict(q='皮', search_fields=search_fields))
        add(f'map-{fields_name}-global-none','map_points',dict(q='不存在词8f0b', search_fields=search_fields))
        for scope, locations in [('small',['天柱竹林']), ('large',['廣州白話']), ('none',['不存在地点'])]:
            add(f'standard-{fields_name}-{scope}-spider','standard_words',
                dict(q='蜘蛛',search_fields=search_fields,locations=locations,limit=None))
    add('entries-both-small-count-hit','items',dict(q='蜘蛛',search_fields=['definition','headword'],locations=['天柱竹林']))
    cases[-1]['cached_count'] = True
    add('entries-both-first-full','items',dict(q='人',search_fields=['definition','headword'],locations=['廣州白話']))
    for name, endpoint, params in [
        ('entries-wildcard','items',dict(q='%',search_fields=['headword'],locations=['天柱竹林'])),
        ('entries-default','items',{}),
        ('map-scope-unchanged','map_points',dict(q='蜘蛛',search_fields=['definition'],locations=['天柱竹林'])),
        ('map-wildcard','map_points',dict(q='%',search_fields=['definition'])),
        ('map-default','map_points',{}),
        ('standard-default-1000','standard_words',dict(limit=1000)),
        ('standard-default-all','standard_words',dict(limit=None)),
    ]:
        add(name,endpoint,params,modes=('time','rss','heap') if endpoint=='standard_words' else ('time','rss'))
    for limit in (1000, None):
        add('standard-spelling-growth-'+str(limit),'standard_words',dict(limit=limit),
            datasets=('spelling',),modes=('time','rss','heap'))
    for endpoint in ('items','standard_words','map_points'):
        add(endpoint+'-high-hit',''+endpoint,
            dict(q='共同',search_fields=['definition','headword'],
                 **({'locations':['廣州白話']} if endpoint != 'map_points' else {}),
                 **({'limit':None} if endpoint == 'standard_words' else {})), datasets=('high_hit',))
    (args.work/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))
    print(json.dumps({'cases':len(cases),'baseline':args.baseline,'work':str(args.work)}))


def batch(args):
    datasets = {'current': args.work/'current.db',
                'growth': args.work/'row-growth.db',
                'spelling':args.work/'spelling-growth.db', 'high_hit':args.work/'high-hit.db'}
    cases = json.loads((args.work/'cases.json').read_text())
    output = []
    for index, job in enumerate(cases):
        if args.only and args.only not in job['name']:
            continue
        for dataset in job['datasets']:
            for mode in job['modes']:
                versions = ('before','after') if index % 2 == 0 else ('after','before')
                pair = {}
                for version in versions:
                    command = [sys.executable, str(Path(__file__).resolve()), '--child', '--source',str(args.work/(version+'.py')),
                               '--db',str(datasets[dataset]),'--job',json.dumps(job,ensure_ascii=False),
                               '--mode',mode,'--rounds',str(args.rounds)]
                    result = subprocess.run(command,capture_output=True,text=True)
                    if result.returncode:
                        raise RuntimeError(f'Benchmark child failed: {job["name"]} {version} {mode}\n{result.stderr}')
                    pair[version] = json.loads(result.stdout)
                assert pair['before']['signature'] == pair['after']['signature'], (job,dataset,mode)
                assert pair['before']['full_rows'] == pair['after']['full_rows'], (job,dataset,'all ordered rows')
                row = dict(name=job['name'],endpoint=job['endpoint'],params=job['params'],dataset=dataset,mode=mode,results=pair)
                output.append(row)
                # Keep verified progress if a later case fails.
                record = dict(platform=platform.platform(),python=sys.version,sqlite=sqlite3.sqlite_version,
                    query_source_sha256={v:hashlib.sha256((args.work/(v+'.py')).read_bytes()).hexdigest()
                                         for v in ('before','after')},
                    limits={p:Path('/sys/fs/cgroup/'+p).read_text().strip() for p in
                        ('cpu.max','memory.max','memory.swap.max') if Path('/sys/fs/cgroup/'+p).exists()},
                    batch_cgroup_peak_bytes=Path('/sys/fs/cgroup/memory.peak').read_text().strip()
                        if Path('/sys/fs/cgroup/memory.peak').exists() else None,
                    batch_memory_events=Path('/sys/fs/cgroup/memory.events').read_text()
                        if Path('/sys/fs/cgroup/memory.events').exists() else None,
                    results=output)
                args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2))
                print(json.dumps(dict(name=job['name'],dataset=dataset,mode=mode,
                    before_ms=pair['before']['median_ms'],after_ms=pair['after']['median_ms'],
                    before_rss_kib=pair['before']['peak_rss_kib'],after_rss_kib=pair['after']['peak_rss_kib'])),flush=True)


def native_sql(args):
    """Replay verified frozen statements in a native stdlib-only container."""
    source = json.loads(args.source.read_text())
    datasets = {'current': args.work/'current.db',
                'growth': args.work/'row-growth.db',
                'spelling':args.work/'spelling-growth.db', 'high_hit':args.work/'high-hit.db'}
    output = []
    for row in source['results']:
        if row['mode'] != 'time':
            continue
        with readonly(datasets[row['dataset']]) as conn:
            sql = {v:row['results'][v]['sql'] for v in ('before','after')}
            samples = {'before':[],'after':[]}
            signatures = {}
            for iteration in range(args.rounds + 1):
                for version in (('before','after') if iteration % 2 == 0 else ('after','before')):
                    start = time.perf_counter()
                    frames = [conn.execute(statement).fetchall() for statement in sql[version]]
                    elapsed = (time.perf_counter()-start)*1000
                    if iteration > 0:
                        samples[version].append(elapsed)
                    if row['endpoint'] == 'items':
                        pages = []
                        for statement, frame in zip(sql[version],frames):
                            if statement.startswith('SELECT COUNT(*)'):
                                assert frame == [(row['results'][version]['total'],)]
                            else:
                                pages = frame
                        signatures[version] = digest(pages)
                    else:
                        # Density probes select the plan, not response rows.
                        signatures[version] = digest([frame for statement,frame in zip(sql[version],frames)
                                                     if not statement.startswith('SELECT SUM(matched)')])
            assert signatures['before'] == signatures['after'], (row['name'],row['dataset'])
            output.append(dict(name=row['name'],dataset=row['dataset'],endpoint=row['endpoint'],
                identical_sql=sql['before']==sql['after'],samples_ms=samples,
                median_ms={v:statistics.median(samples[v]) for v in samples},
                plans={v:[conn.execute('EXPLAIN QUERY PLAN '+s).fetchall() for s in sql[v]] for v in sql}))
            print(json.dumps(output[-1],ensure_ascii=False),flush=True)
    args.output.write_text(json.dumps(dict(platform=platform.platform(),sqlite=sqlite3.sqlite_version,
        limits={p:Path('/sys/fs/cgroup/'+p).read_text().strip() for p in ('cpu.max','memory.max','memory.swap.max')},
        batch_peak_rss_kib=rss_kib(),results=output),ensure_ascii=False,indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--batch',action='store_true')
    parser.add_argument('--child',action='store_true')
    parser.add_argument('--native-sql',action='store_true')
    parser.add_argument('--baseline',default='29ebfa0')
    parser.add_argument('--work',type=Path,default=ROOT/'outputs/vocabulary-release-20261101')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--db',type=Path)
    parser.add_argument('--job')
    parser.add_argument('--mode',choices=('time','rss','heap'))
    parser.add_argument('--rounds',type=int,default=5)
    parser.add_argument('--only',help='Run only case names containing this text')
    args=parser.parse_args()
    if args.prepare:
        prepare(args)
    elif args.batch:
        batch(args)
    elif args.child:
        child(args)
    elif args.native_sql:
        native_sql(args)
    else:
        parser.error('choose --prepare, --batch or --child')


if __name__ == '__main__':
    main()
