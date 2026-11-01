"""Offline standard-word memory release: actual functions, exact full responses.

Prepare locally; batch inside2CPU/2GiB/no-swap/network container. SQL is unchanged.
Time is alternating actual calls; RSS and Python allocations are fresh, separate
processes. No production connections, schema changes, caches, or disk aggregation.
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import statistics
import subprocess
import sys
import time
import tracemalloc
from types import SimpleNamespace

import benchmark_vocabulary_release as base

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'outputs/vocabulary-standard-memory-20261101'
FIXTURES=ROOT/'outputs/vocabulary-release-20261101'


def paths(work):
    return {'current':FIXTURES/'current.db','row_growth':FIXTURES/'row-growth.db',
            'spelling_growth':FIXTURES/'spelling-growth.db','location_growth':work/'location-growth.db'}


def check(work):
    meta=json.loads((work/'source.json').read_text())
    assert hashlib.sha256((ROOT/'app/service/vocabulary/query.py').read_bytes()).hexdigest()==meta['sha256']['after.py']
    for version in ['before','after']:
        assert hashlib.sha256((work/(version+'.py')).read_bytes()).hexdigest()==meta['sha256'][version+'.py']


def metadata(work):
    return dict(source=json.loads((work/'source.json').read_text()),python=sys.version,
        sqlite=sqlite3.sqlite_version,platform=platform.platform(),limits={p:Path('/sys/fs/cgroup/'+p).read_text().strip()
        for p in ['cpu.max','memory.max','memory.swap.max','memory.peak','memory.events'] if Path('/sys/fs/cgroup/'+p).exists()})


def prepare(args):
    work=args.work;work.mkdir(parents=True,exist_ok=True)
    before=subprocess.check_output(['git','show','69cfa47:app/service/vocabulary/query.py'],cwd=ROOT,text=True)
    (work/'before.py').write_text(before)
    (work/'after.py').write_bytes((ROOT/'app/service/vocabulary/query.py').read_bytes())
    loc=work/'location-growth.db'
    if not loc.exists():
        with base.readonly(FIXTURES/'current.db') as src,sqlite3.connect(loc) as dest:src.backup(dest)
        with sqlite3.connect(loc) as dest:
            dest.execute("UPDATE vocabulary_entries SET location_name='地点'||printf('%04d',id%1024)")
    fixtures={}
    for label,path in paths(work).items():
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        with base.readonly(path) as c:
            rows=c.execute('SELECT COUNT(*),COUNT(DISTINCT standard_word),COUNT(DISTINCT location_name) FROM vocabulary_entries').fetchone()
        fixtures[label]=dict(sha256=h.hexdigest(),bytes=path.stat().st_size,entries=rows[0],spellings=rows[1],locations=rows[2])
    (work/'source.json').write_text(json.dumps(dict(baseline='69cfa47',fixtures=fixtures,
        sha256={n:hashlib.sha256((work/n).read_bytes()).hexdigest() for n in ['before.py','after.py']}),ensure_ascii=False,indent=2))
    jobs=[]
    for dataset in paths(work):
        for limit in [1000,None]:
            jobs.append(dict(name='all-'+str(limit),dataset=dataset,endpoint='standard_words',params=dict(limit=limit),resources=True))
    for dataset in ['current','spelling_growth']:
        for name,params in [
            ('definition',dict(q='太阳',search_fields=['definition'])),
            ('headword',dict(q='日头',search_fields=['headword'])),
            ('both-small',dict(q='蜘蛛',search_fields=['definition','headword'],locations=['天柱竹林','息烽'])),
            ('both-wide',dict(q='蜘蛛',search_fields=['definition','headword'],locations=['廣州','香港'])),
            ('all-fields',dict(q='人')),
            ('wildcard',dict(q='%',search_fields=['headword'])),
            ('empty',dict(q='不存在词零命中')),
            ('province',dict(province='廣東')),
        ]:jobs.append(dict(name=name,dataset=dataset,endpoint='standard_words',params=dict(params,limit=None),resources=False))
    (work/'jobs.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2))
    print(json.dumps(dict(jobs=len(jobs),fixtures=fixtures),ensure_ascii=False))


def batch(args):
    check(args.work);output=[]
    modules={v:base.load(args.work/(v+'.py')) for v in ['before','after']}
    for job in json.loads((args.work/'jobs.json').read_text()):
        conns={v:base.readonly(paths(args.work)[job['dataset']]) for v in modules}
        sessions={v:SimpleNamespace(connection=lambda v=v:SimpleNamespace(connection=conns[v])) for v in modules}
        pair={v:dict(samples_ms=[],cpu_ms=[]) for v in modules}
        # Complete ordered payload equality incl. all groups/variants/counts.
        for v in modules:
            sql=[];conns[v].set_trace_callback(sql.append)
            r=modules[v].query_vocabulary_standard_words(session=sessions[v],**job['params'])
            conns[v].set_trace_callback(None)
            pair[v].update(signature=base.digest(r),total=r.total,returned=len(r.standard_words),sql=sql);del r
        assert pair['before']['signature']==pair['after']['signature'],job
        assert pair['before']['sql']==pair['after']['sql'],(job,'SQL must not change')
        for n in range(args.rounds+1):
            for v in (list(modules) if n%2 else list(modules)[::-1]):
                gc.collect();t=time.perf_counter();cpu=time.process_time()
                r=modules[v].query_vocabulary_standard_words(session=sessions[v],**job['params'])
                elapsed=(time.perf_counter()-t)*1000;cpums=(time.process_time()-cpu)*1000
                if n:pair[v]['samples_ms'].append(elapsed);pair[v]['cpu_ms'].append(cpums)
                del r
        for v in modules:
            pair[v]['median_ms']=statistics.median(pair[v]['samples_ms'])
            pair[v]['median_cpu_ms']=statistics.median(pair[v]['cpu_ms']);conns[v].close()
        output.append(dict(job,mode='time',results=pair))
        print(json.dumps(dict(name=job['name'],dataset=job['dataset'],ms={v:pair[v]['median_ms'] for v in modules}),ensure_ascii=False),flush=True)
        # Separate source processes exclude before/after retained outputs/modules.
        if job['resources']:
            for mode in ['rss','heap']:
                pair={}
                for version in ['before','after']:
                    p=subprocess.run([sys.executable,__file__,'--child','--source',str(args.work/(version+'.py')),
                        '--db',str(paths(args.work)[job['dataset']]),'--job',json.dumps(job,ensure_ascii=False),'--mode',mode,'--rounds','1'],capture_output=True,text=True)
                    if p.returncode:raise RuntimeError((job,version,p.stderr))
                    pair[version]=json.loads(p.stdout)
                assert pair['before']['signature']==pair['after']['signature'],(job,mode)
                assert pair['before']['sql']==pair['after']['sql'],(job,mode,'SQL')
                output.append(dict(job,mode=mode,results=pair))
                print(json.dumps(dict(name=job['name'],dataset=job['dataset'],mode=mode,
                    rss={v:pair[v]['peak_rss_kib'] for v in modules},heap={v:pair[v]['python_peak_bytes'] for v in modules}),ensure_ascii=False),flush=True)
        args.output.write_text(json.dumps(dict(**metadata(args.work),results=output),ensure_ascii=False,indent=2))
    check(args.work)


def resource_child(args):
    # /proc VmHWM is reset on exec; ru_maxrss may include a pre-exec parent
    # high-water value when the coordinator has already run large aggregates.
    module=base.load(args.source);job=json.loads(args.job)
    conn=base.readonly(args.db);session=SimpleNamespace(connection=lambda:SimpleNamespace(connection=conn))
    def status():
        return {k:int(v.strip().split()[0]) for k,v in (line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines()) if k in ['VmRSS','VmHWM']}
    gc.collect();pre=status();io_before=base.proc_io()
    if args.mode=='heap':tracemalloc.start()
    start=time.perf_counter();result=module.query_vocabulary_standard_words(session=session,**job['params']);ms=(time.perf_counter()-start)*1000
    heap=tracemalloc.get_traced_memory()[1] if args.mode=='heap' else None
    if args.mode=='heap':tracemalloc.stop()
    post=status();io_after=base.proc_io()
    signature=base.digest(result);total=result.total;returned=len(result.standard_words);del result
    statements=[];conn.set_trace_callback(statements.append)
    result=module.query_vocabulary_standard_words(session=session,**job['params']);conn.set_trace_callback(None)
    assert base.digest(result)==signature
    print(json.dumps(dict(median_ms=ms,signature=signature,total=total,returned=returned,sql=[st for st in statements if st.startswith(('SELECT','WITH'))],
        peak_rss_kib=post['VmHWM'],pre_query_peak_rss_kib=pre['VmHWM'],proc_status_before=pre,proc_status_after=post,
        rusage_peak_rss_kib=base.rss_kib(),python_peak_bytes=heap,query_process_io_delta={k:str(int(io_after[k])-int(io_before[k])) for k in io_after}),ensure_ascii=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--batch',action='store_true')
    p.add_argument('--work',type=Path,default=WORK);p.add_argument('--output',type=Path);p.add_argument('--rounds',type=int,default=7)
    p.add_argument('--child',action='store_true');p.add_argument('--source',type=Path);p.add_argument('--db',type=Path);p.add_argument('--job');p.add_argument('--mode')
    a=p.parse_args()
    if a.prepare:prepare(a)
    elif a.batch:batch(a)
    elif a.child:resource_child(a)

if __name__=='__main__':main()
