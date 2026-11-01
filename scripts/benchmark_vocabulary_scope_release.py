"""Measure actual committed scope queries, with complete-result verification.

Local only. --prepare freezes before/after sources and cases. Run --batch in
an isolated 2-CPU/2-GiB container. --native-sql needs only stdlib + this and the
previous release helper script. All database inputs are read-only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time
import gc
import tracemalloc

import benchmark_vocabulary_release as base

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'outputs/vocabulary-scoped-release-20261101'


def prepare(args):
    args.work.mkdir(parents=True,exist_ok=True)
    before=subprocess.check_output(['git','show','b8d90fe:app/service/vocabulary/query.py'],cwd=ROOT,text=True)
    (args.work/'before.py').write_text(before)
    (args.work/'after.py').write_bytes((ROOT/'app/service/vocabulary/query.py').read_bytes())
    (args.work/'scope_plan.py').write_bytes((ROOT/'app/service/vocabulary/scope_plan.py').read_bytes())
    jobs=[]
    corpus=json.loads((ROOT/'docs/vocabulary-location-scope-exploration-2026-11-01.json').read_text())
    cases=next(e['results'] for e in corpus['experiments'] if e['source']=='growth-final.json')
    for row in cases:
        if row['fields'] not in [['definition'],['headword'],['definition','headword']]:continue
        # All measured content fields/scopes/zero-hit/full-page shapes on growth.
        if row['q']=='共同':datasets=['high_hit']
        elif row['scope'] in ['small2','small8','large1','wide22']:
            datasets=['growth']
            if row['fields']==['definition','headword'] and row['q'] in ['蜘蛛','人']:
                datasets+=['current']
        elif row['fields']==['definition','headword']:
            datasets=['growth']
        else:continue
        params=dict(q=row['q'],search_fields=row['fields'],locations=row['locations'])
        endpoint={'entries':'items','standard-words':'standard_words','map-points':'map_points'}[row['endpoint']]
        if endpoint=='standard_words':params['limit']=None
        modes=['time']
        if row['fields']==['definition','headword'] and row['q'] in ['蜘蛛','共同']:
            modes+=['rss']
        jobs.append(dict(name=row['name'],endpoint=endpoint,params=params,datasets=datasets,modes=modes))
    module=base.load(args.work/'before.py')
    from types import SimpleNamespace
    with base.readonly(args.fixtures/'row-growth.db') as conn:
        session=SimpleNamespace(connection=lambda:SimpleNamespace(connection=conn))
        for scope in ['small2','small8','large1','wide22']:
            for term in ['蜘蛛','人']:
                original=next(j for j in jobs if j['endpoint']=='items' and j['name']==scope+'-definition+headword-'+term)
                job=dict(original,name=original['name']+'-count-hit',datasets=['growth'],modes=['time','rss'])
                job['cached_total']=module.query_vocabulary_items(session=session,**job['params']).total
                jobs.append(job)
    for endpoint in ['standard_words','map_points']:
        jobs.append(dict(name='no-q-all',endpoint=endpoint,params={'limit':None} if endpoint=='standard_words' else {},datasets=['current'],modes=['time','rss','heap'] if endpoint=='standard_words' else ['time','rss']))
    (args.work/'jobs.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2))
    (args.work/'source.json').write_text(json.dumps(dict(baseline='b8d90fe',after_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sha256={n:hashlib.sha256((args.work/n).read_bytes()).hexdigest() for n in ['before.py','after.py','scope_plan.py']},note='query imports final scope_plan from read-only workspace; frozen copy/hash retained'),indent=2))
    print(json.dumps({'jobs':len(jobs),'time_pairs':sum(len(j['datasets']) for j in jobs)},ensure_ascii=False))


def proc_status():
    path=Path('/proc/self/status')
    return {k:int(v.strip().split()[0]) for k,v in (line.split(':',1) for line in path.read_text().splitlines()) if k in {'VmHWM','VmRSS'}} if path.exists() else {}


def child(args):
    from types import SimpleNamespace
    module=base.load(args.source)
    job=json.loads(args.job)
    conn=base.readonly(args.db)
    session=SimpleNamespace(connection=lambda:SimpleNamespace(connection=conn))
    query=getattr(module,'query_vocabulary_'+job['endpoint'])
    params=dict(job['params'])
    if 'cached_total' in job:params['_count_resolver']=lambda *_:job['cached_total']
    gc.collect()
    before_rss=base.rss_kib();before_status=proc_status();before_io=base.proc_io()
    if args.mode=='heap':tracemalloc.start()
    samples=[]
    for _ in range(args.rounds if args.mode=='time' else 1):
        start=time.perf_counter();result=query(session=session,**params);samples.append((time.perf_counter()-start)*1000)
        if args.mode=='time':del result;gc.collect()
    heap=tracemalloc.get_traced_memory()[1] if args.mode=='heap' else None
    if args.mode=='heap':tracemalloc.stop()
    peak_rss=base.rss_kib();after_status=proc_status();after_io=base.proc_io()
    # Verification is outside measured CPU, RSS and allocation intervals.
    statements=[];conn.set_trace_callback(statements.append)
    result=query(session=session,**params);conn.set_trace_callback(None)
    full_rows=None
    sql=[s for s in statements if s.startswith(('SELECT','WITH'))]
    if job['endpoint']=='items':
        pages=[s for s in sql if 'vocabulary_scope_plan' not in s and 'vocabulary_scope_count' not in s and not s.startswith('SELECT COUNT(*)')]
        if pages:
            all_sql=re.sub(r'LIMIT \d+ OFFSET \d+','LIMIT -1 OFFSET 0',pages[-1],count=1)
            count=0;h=hashlib.sha256()
            for row in conn.execute(all_sql):count+=1;h.update(repr(row).encode())
            assert count==result.total
            full_rows=[count,h.hexdigest()]
        else:
            assert result.total==0
            full_rows=[0,hashlib.sha256().hexdigest()]
    print(json.dumps(dict(median_ms=statistics.median(samples),samples_ms=samples,first_ms=samples[0],peak_rss_kib=peak_rss,pre_query_peak_rss_kib=before_rss,pre_query_proc_status_kib=before_status,post_query_proc_status_kib=after_status,python_peak_bytes=heap,query_process_io_delta={k:int(after_io[k])-int(before_io[k]) for k in after_io},signature=base.digest(result),full_rows=full_rows,total=result.total if hasattr(result,'total') else result.total_entries,returned=len(result.items) if hasattr(result,'items') else len(result.standard_words) if hasattr(result,'standard_words') else len(result.points),sql=sql),ensure_ascii=False))


def metadata(args):
    return dict(platform=platform.platform(),python=sys.version,sqlite=__import__('sqlite3').sqlite_version,
                source=json.loads((args.work/'source.json').read_text()),
                limits={p:Path('/sys/fs/cgroup/'+p).read_text().strip() for p in ['cpu.max','memory.max','memory.swap.max','memory.peak','memory.events'] if Path('/sys/fs/cgroup/'+p).exists()})


def batch(args):
    source=json.loads((args.work/'source.json').read_text())
    def verify_sources():
        for frozen,live in [('after.py','query.py'),('scope_plan.py','scope_plan.py')]:
            expected=source['sha256'][frozen]
            assert hashlib.sha256((args.work/frozen).read_bytes()).hexdigest()==expected
            assert hashlib.sha256((ROOT/'app/service/vocabulary'/live).read_bytes()).hexdigest()==expected
    verify_sources()
    paths={'current':'current.db','growth':'row-growth.db','high_hit':'high-hit.db'}
    output=[]
    for index,job in enumerate(json.loads((args.work/'jobs.json').read_text())):
        for dataset in job['datasets']:
            for mode in job['modes']:
                pair={}
                for version in (['before','after'] if index%2==0 else ['after','before']):
                    command=[sys.executable,__file__,'--child','--source',str(args.work/(version+'.py')),'--db',str(args.fixtures/paths[dataset]),'--job',json.dumps(job,ensure_ascii=False),'--mode',mode,'--rounds',str(args.rounds)]
                    p=subprocess.run(command,capture_output=True,text=True)
                    if p.returncode:raise RuntimeError(str((job['name'],version,mode))+p.stderr)
                    pair[version]=json.loads(p.stdout)
                assert pair['before']['signature']==pair['after']['signature'],(job,dataset,mode,'result')
                assert pair['before']['full_rows']==pair['after']['full_rows'],(job,dataset,mode,'full ordered rows')
                output.append(dict(name=job['name'],endpoint=job['endpoint'],params=job['params'],dataset=dataset,mode=mode,count_cache_hit='cached_total' in job,results=pair))
                args.output.write_text(json.dumps(dict(**metadata(args),results=output),ensure_ascii=False,indent=2))
                print(json.dumps(dict(name=job['name'],endpoint=job['endpoint'],dataset=dataset,mode=mode,before_ms=pair['before']['median_ms'],after_ms=pair['after']['median_ms']),ensure_ascii=False),flush=True)
    verify_sources()


def native(args):
    paths={'current':'current.db','growth':'row-growth.db','high_hit':'high-hit.db'}
    output=[]
    for row in json.loads(args.source.read_text())['results']:
        if row['mode']!='time':continue
        with base.readonly(args.fixtures/paths[row['dataset']]) as conn:
            samples={v:[] for v in ['before','after']};signatures={}
            for iteration in range(args.rounds+1):
                for version in (['before','after'] if iteration%2==0 else ['after','before']):
                    start=time.perf_counter();frames=[]
                    for sql in row['results'][version]['sql']:
                        values=conn.execute(sql).fetchall()
                        # Planner rows select a path, not part of the response.
                        if ('vocabulary_scope_plan' not in sql and 'vocabulary_scope_count' not in sql
                            and not sql.startswith(('SELECT COUNT(*)','SELECT SUM(matched)'))):frames.append(values)
                    elapsed=(time.perf_counter()-start)*1000
                    if iteration:samples[version].append(elapsed)
                    signatures[version]=base.digest(frames)
            assert signatures['before']==signatures['after'],(row['name'],row['dataset'],'SQL frames')
            output.append(dict(name=row['name'],endpoint=row['endpoint'],dataset=row['dataset'],count_cache_hit=row['count_cache_hit'],samples_ms=samples,median_ms={v:statistics.median(s) for v,s in samples.items()},identical_sql=row['results']['before']['sql']==row['results']['after']['sql']))
            args.output.write_text(json.dumps(dict(**metadata(args),results=output),ensure_ascii=False,indent=2))
            print(json.dumps(output[-1],ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser()
    for flag in ['prepare','batch','native-sql','child']:p.add_argument('--'+flag,action='store_true')
    p.add_argument('--work',type=Path,default=WORK);p.add_argument('--fixtures',type=Path,default=ROOT/'outputs/vocabulary-release-20261101');p.add_argument('--source',type=Path);p.add_argument('--db',type=Path);p.add_argument('--job');p.add_argument('--mode');p.add_argument('--output',type=Path);p.add_argument('--rounds',type=int,default=5)
    a=p.parse_args()
    if a.prepare:prepare(a)
    elif a.child:child(a)
    elif a.batch:batch(a)
    elif a.native_sql:native(a)

if __name__=='__main__':main()
