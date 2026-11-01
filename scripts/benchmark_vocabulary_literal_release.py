"""Freeze and measure actual entries literal-scan functions; strictly offline.

Prepare with project Python. Batch service runs use project dependencies; native
SQL replay needs only stdlib. Restrict containers to 2 CPU/2GiB/no swap/network.
Separate subprocesses measure time, RSS and heap, verifying outside intervals.
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import platform
import re
import sqlite3
import statistics
import subprocess
import sys
import time
import tracemalloc
from types import SimpleNamespace

import benchmark_vocabulary_release as base

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'outputs/vocabulary-global-20261101'
FIXTURES = ROOT / 'outputs/vocabulary-release-20261101'


def metadata(work):
    return dict(platform=platform.platform(), python=sys.version, sqlite=sqlite3.sqlite_version,
        source=json.loads((work/'source.json').read_text()),
        limits={p:Path('/sys/fs/cgroup/'+p).read_text().strip() for p in
            ['cpu.max','memory.max','memory.swap.max','memory.peak','memory.events']
            if Path('/sys/fs/cgroup/'+p).exists()})


def prepare(args):
    work=args.work;work.mkdir(parents=True,exist_ok=True)
    before=subprocess.check_output(['git','show','0ff288e:app/service/vocabulary/query.py'],cwd=ROOT,text=True)
    (work/'before.py').write_text(before)
    for live,frozen in [('query.py','after.py'),('literal_scan.py','literal_scan.py'),('scope_plan.py','scope_plan.py')]:
        (work/frozen).write_bytes((ROOT/'app/service/vocabulary'/live).read_bytes())
    sources={n:hashlib.sha256((work/n).read_bytes()).hexdigest() for n in ['before.py','after.py','literal_scan.py','scope_plan.py']}
    (work/'source.json').write_text(json.dumps(dict(baseline='0ff288e',sha256=sources),indent=2))
    with base.readonly(FIXTURES/'current.db') as c:
        names=[r[0] for r in c.execute('SELECT location_name FROM vocabulary_entries GROUP BY location_name ORDER BY COUNT(*) DESC LIMIT 22')]
    jobs=[]
    for scope,locations in [('global',[]),('wide22',names)]:
        for fields in [['definition'],['headword'],['definition','headword'],['all']]:
            for q in ['蜘蛛','皮','人','不存在词零命中','什么','山东']:
                jobs.append(dict(name=scope+'-'+'+'.join(fields)+'-'+q,
                    params=dict(q=q,locations=locations,search_fields=fields),datasets=['current','growth']))
    for scope,locations in [('small2',['天柱竹林','息烽']),('large1',names[:1])]:
        for fields in [['definition'],['headword'],['definition','headword']]:
            for q in ['蜘蛛','人','不存在词零命中']:
                jobs.append(dict(name=scope+'-'+'+'.join(fields)+'-'+q,
                    params=dict(q=q,locations=locations,search_fields=fields),datasets=['growth']))
    for name,params in [
        ('empty',{}),('empty-location',{'locations':names[:1]}),
        ('ascii',dict(q='A',search_fields=['headword'])),
        ('wildcard',dict(q='%',search_fields=['headword'])),
        ('underscore',dict(q='_',search_fields=['definition','headword'])),
        ('nul',dict(q='蜘\x00蛛',search_fields=['headword'])),
        ('province',dict(q='人',province='廣東',search_fields=['headword'])),
        ('region',dict(q='人',regions=['嶺南'],search_fields=['headword'])),
        ('exact-word',dict(q='人',standard_words=['人'],search_fields=['headword'])),
        ('page2',dict(q='蜘蛛',page=2,search_fields=['headword'])),
        ('pronunciation',dict(q='a',search_fields=['pronunciation'])),
        ('detail',dict(q='蜘蛛',search_fields=['detail'])),
    ]:jobs.append(dict(name=name,params=params,datasets=['growth']))
    for fields in [['definition'],['headword'],['definition','headword'],['all']]:
        jobs.append(dict(name='dense-'+'+'.join(fields),params=dict(q='共同',search_fields=fields),datasets=['high_hit','skew']))
    # A dense old half and sparse recent half; only this offline copy is written.
    skew=work/'skew.db'
    if not skew.exists():
        with base.readonly(FIXTURES/'high-hit.db') as src,sqlite3.connect(skew) as dest:src.backup(dest)
        with sqlite3.connect(skew) as dest:
            max_id=dest.execute('SELECT MAX(id) FROM vocabulary_entries').fetchone()[0]
            dest.execute("UPDATE vocabulary_entries SET standard_word='普通',local_expression='其他',ipa='',notes='',informations='' WHERE id>?",(max_id//2,))
    module=base.load(work/'before.py')
    with base.readonly(FIXTURES/'row-growth.db') as c:
        session=SimpleNamespace(connection=lambda:SimpleNamespace(connection=c))
        for scope,locations in [('global',[]),('wide22',names)]:
            for word in ['蜘蛛','人']:
                params=dict(q=word,locations=locations,search_fields=['definition','headword'])
                total=module.query_vocabulary_items(session=session,**params).total
                jobs.append(dict(name=scope+'-both-'+word+'-count-hit',params=params,datasets=['growth'],cached_total=total))
    (work/'jobs-release.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2))
    print(json.dumps(dict(jobs=len(jobs),pairs=sum(len(j['datasets']) for j in jobs))))


def child(args):
    module=base.load(args.source)
    job=json.loads(args.job);params=dict(job['params'])
    conn=base.readonly(args.db)
    session=SimpleNamespace(connection=lambda:SimpleNamespace(connection=conn))
    if 'cached_total' in job:params['_count_resolver']=lambda *_:job['cached_total']
    query=module.query_vocabulary_items
    gc.collect();before_rss=base.rss_kib();before_io=base.proc_io()
    if args.mode=='heap':tracemalloc.start()
    samples=[];cpu_start=time.process_time()
    for _ in range(args.rounds if args.mode=='time' else 1):
        start=time.perf_counter();result=query(session=session,**params);samples.append((time.perf_counter()-start)*1000)
        if args.mode=='time':del result;gc.collect()
    cpu=time.process_time()-cpu_start
    heap=tracemalloc.get_traced_memory()[1] if args.mode=='heap' else None
    if args.mode=='heap':tracemalloc.stop()
    rss=base.rss_kib();after_io=base.proc_io()
    sql=[];conn.set_trace_callback(sql.append);result=query(session=session,**params);conn.set_trace_callback(None)
    actual=[s for s in sql if s.startswith(('SELECT','WITH'))]
    page=[s for s in actual if 'SELECT e.id, e.standard_word,' in s and 'vocabulary_literal_probe' not in s]
    full=None
    if page:
        full_sql=re.sub(r'LIMIT \d+ OFFSET \d+','LIMIT -1 OFFSET 0',page[-1],count=1)
        h=hashlib.sha256();n=0
        for row in conn.execute(full_sql):h.update(repr(row).encode());n+=1
        assert n==result.total,(job,n,result.total)
        full=[n,h.hexdigest()]
    elif result.total==0:full=[0,hashlib.sha256().hexdigest()]
    print(json.dumps(dict(median_ms=statistics.median(samples),first_ms=samples[0],samples_ms=samples,cpu_ms=cpu*1000,
        peak_rss_kib=rss,pre_query_peak_rss_kib=before_rss,python_peak_bytes=heap,
        io_delta={k:int(after_io[k])-int(before_io[k]) for k in after_io},
        signature=base.digest(result),total=result.total,returned=len(result.items),full_rows=full,sql=actual),ensure_ascii=False))


def batch(args):
    jobs=json.loads((args.work/'jobs-release.json').read_text());output=[]
    paths=dict(current=FIXTURES/'current.db',growth=FIXTURES/'row-growth.db',high_hit=FIXTURES/'high-hit.db',skew=args.work/'skew.db')
    for n,job in enumerate(jobs):
        for dataset in job['datasets']:
            modes=['time']
            if (dataset=='growth' and job['name'] in ['global-headword-蜘蛛','global-all-不存在词零命中','wide22-definition+headword-皮','global-both-蜘蛛-count-hit']) or dataset in ['high_hit','skew']:
                modes+=['rss','heap']
            for mode in modes:
                pair={}
                for version in (['before','after'] if n%2 else ['after','before']):
                    p=subprocess.run([sys.executable,__file__,'--child','--work',str(args.work),'--source',str(args.work/(version+'.py')),'--db',str(paths[dataset]),'--job',json.dumps(job,ensure_ascii=False),'--mode',mode,'--rounds',str(args.rounds)],capture_output=True,text=True)
                    if p.returncode:raise RuntimeError((job['name'],version,p.stderr))
                    pair[version]=json.loads(p.stdout)
                for key in ['signature','full_rows','total']:assert pair['before'][key]==pair['after'][key],(job,dataset,key)
                output.append(dict(name=job['name'],params=job['params'],dataset=dataset,mode=mode,results=pair))
                args.output.write_text(json.dumps(dict(**metadata(args.work),results=output),ensure_ascii=False,indent=2))
                print(json.dumps(dict(name=job['name'],dataset=dataset,mode=mode,before=pair['before']['median_ms'],after=pair['after']['median_ms']),ensure_ascii=False),flush=True)
    check_sources(args.work)


def check_sources(work):
    for frozen,live in [('after.py','query.py'),('literal_scan.py','literal_scan.py'),('scope_plan.py','scope_plan.py')]:
        expected=json.loads((work/'source.json').read_text())['sha256'][frozen]
        assert hashlib.sha256((work/frozen).read_bytes()).hexdigest()==expected
        assert hashlib.sha256((ROOT/'app/service/vocabulary'/live).read_bytes()).hexdigest()==expected


def native(args):
    paths=dict(current=FIXTURES/'current.db',growth=FIXTURES/'row-growth.db',high_hit=FIXTURES/'high-hit.db',skew=args.work/'skew.db')
    output=[]
    for row in json.loads(args.source.read_text())['results']:
        if row['mode']!='time':continue
        with base.readonly(paths[row['dataset']]) as conn:
            samples={v:[] for v in ['before','after']}
            for n in range(args.rounds+1):
                for version in (list(samples) if n%2 else list(samples)[::-1]):
                    start=time.perf_counter()
                    for sql in row['results'][version]['sql']:conn.execute(sql).fetchall()
                    if n:samples[version].append((time.perf_counter()-start)*1000)
            output.append(dict(name=row['name'],dataset=row['dataset'],median_ms={v:statistics.median(s) for v,s in samples.items()},samples_ms=samples,
                identical_sql=row['results']['before']['sql']==row['results']['after']['sql']))
            args.output.write_text(json.dumps(dict(**metadata(args.work),results=output),ensure_ascii=False,indent=2))
            print(json.dumps(output[-1],ensure_ascii=False),flush=True)
    check_sources(args.work)


def paired_time(args):
    """Alternate real before/after calls to reduce emulator scheduling bias.

    Keep separately measured first-call/RSS/heap data. Recheck every response
    digest and traced SQL against the frozen subprocess batch before replacing
    only warmed timing samples. No concurrent benchmarking is performed.
    """
    data=json.loads(args.source.read_text())
    paths=dict(current=FIXTURES/'current.db',growth=FIXTURES/'row-growth.db',high_hit=FIXTURES/'high-hit.db',skew=args.work/'skew.db')
    modules={v:base.load(args.work/(v+'.py')) for v in ['before','after']}
    for row in data['results']:
        if row['mode']!='time':continue
        conns={v:base.readonly(paths[row['dataset']]) for v in modules}
        sessions={v:SimpleNamespace(connection=lambda v=v:SimpleNamespace(connection=conns[v])) for v in modules}
        params=dict(row['params'])
        if row['name'].endswith('-count-hit'):
            total=row['results']['before']['total']
            params['_count_resolver']=lambda *_:total
        samples={v:[] for v in modules};cpu={v:[] for v in modules}
        for n in range(args.rounds+1):
            for v in (list(modules) if n%2 else list(modules)[::-1]):
                gc.collect();start=time.perf_counter();cpustart=time.process_time()
                result=modules[v].query_vocabulary_items(session=sessions[v],**params)
                elapsed=(time.perf_counter()-start)*1000;cpums=(time.process_time()-cpustart)*1000
                assert base.digest(result)==row['results'][v]['signature'],(row['name'],v)
                if n:samples[v].append(elapsed);cpu[v].append(cpums)
        for v in modules:
            sql=[];conns[v].set_trace_callback(sql.append)
            modules[v].query_vocabulary_items(session=sessions[v],**params)
            actual=[st for st in sql if st.startswith(('SELECT','WITH'))]
            assert actual==row['results'][v]['sql'],(row['name'],v,'SQL drift')
            old=row['results'][v]
            old['independent_process_median_ms']=old['median_ms']
            old['independent_process_samples_ms']=old['samples_ms']
            old['median_ms']=statistics.median(samples[v]);old['samples_ms']=samples[v]
            old['median_cpu_ms']=statistics.median(cpu[v]);old['cpu_samples_ms']=cpu[v]
            conns[v].close()
        data['paired_time_method']='One process, fresh before/after SQLite connections per case; one warmup, alternating calls; RSS/heap/first remain separate original subprocesses.'
        args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2))
        print(json.dumps(dict(name=row['name'],dataset=row['dataset'],median_ms={v:row['results'][v]['median_ms'] for v in modules}),ensure_ascii=False),flush=True)
    check_sources(args.work)


def main():
    p=argparse.ArgumentParser()
    for flag in ['prepare','batch','child','native','paired-time']:p.add_argument('--'+flag,action='store_true')
    p.add_argument('--work',type=Path,default=DEFAULT);p.add_argument('--source',type=Path);p.add_argument('--output',type=Path);p.add_argument('--db',type=Path);p.add_argument('--job');p.add_argument('--mode');p.add_argument('--rounds',type=int,default=5)
    a=p.parse_args()
    if a.prepare:prepare(a)
    elif a.child:child(a)
    elif a.batch:batch(a)
    elif a.native:native(a)
    elif a.paired_time:paired_time(a)

if __name__=='__main__':main()
