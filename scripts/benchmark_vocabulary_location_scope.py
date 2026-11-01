"""Offline scope-plan experiments. No business code changes or server access.

--prepare imports the current query builder and freezes literal SQL locally.
--run uses only stdlib, read-only fixture DBs and independent RSS processes.
All LIMITs below concern sampling/test pages; result parity checks read all hits.
"""
import argparse
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
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'outputs/vocabulary-scope-20261101'


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)


def freeze(conn, sql, values):
    trace=[]
    conn.set_trace_callback(trace.append)
    # EXPLAIN does not emit expanded bindings, so use a false outer query.
    conn.execute('SELECT * FROM ('+sql+') LIMIT 0', values).fetchall()
    conn.set_trace_callback(None)
    result=trace[-1]
    return result[len('SELECT * FROM ('):-len(') LIMIT 0')]


def prepare(args):
    sys.path.insert(0,str(ROOT))
    from app.service.vocabulary import query as q
    args.work.mkdir(parents=True,exist_ok=True)
    db=ROOT/'outputs/vocabulary-release-20261101/current.db'
    conn=readonly(db)
    names=[r[0] for r in conn.execute('SELECT location_name FROM vocabulary_entries GROUP BY location_name ORDER BY COUNT(*) DESC')]
    scopes={'small2':['天柱竹林','息烽'], 'large1':['廣州白話'],
            'small8':names[-8:], 'wide22':names[:22], 'overlap':['香港','香港客家'],
            'missing':['不存在地点'], 'metadata':['廣西'], 'metadata_broad':['廣東'], 'all29':names}
    entry=('e.id, e.standard_word, e.local_expression, e.ipa, e.notes, e.informations, e.location_name')
    loc=('l.coordinates, l.province, l.city, l.county, l.town, l.administrative_village, l.natural_village, l.yindian_region, l.atlas_region ')
    join='LEFT JOIN vocabulary_locations l ON l.user_id = e.user_id AND l.location_name = e.location_name '
    jobs=[]
    # Each primary shape includes scarce, common, absent and script-variant terms.
    cases=[]
    for scope in ['small2','large1','small8','wide22']:
        for fields in [['definition'],['headword'],['definition','headword']]:
            for keyword in ['蜘蛛','人','不存在词8f0b']:
                cases.append((scope,fields,keyword))
    for scope in ['overlap','missing','metadata','metadata_broad','all29']:
        for keyword in ['蜘蛛','人']:
            cases.append((scope,['definition','headword'],keyword))
    for fields in [list(q.DEFAULT_SEARCH_FIELDS),['pronunciation'],['detail']]:
        cases.append(('wide22',fields,'a' if fields==['pronunciation'] else '蜘蛛'))
    for scope in ['small2','small8','large1','wide22']:
        cases.append((scope,['definition','headword'],'共同'))
    for scope,fields,keyword in cases:
        locations=scopes[scope]
        content,cv=q._build_filter_clause(q=keyword,search_fields=fields,locations=[])
        scope_sql,sv=q._build_filter_clause(q=None,search_fields=fields,locations=locations)
        where,values=q._build_filter_clause(q=keyword,search_fields=fields,locations=locations)
        nc,nv,mc,mv=[],[],[],[]
        q._append_like_group(clauses=nc,values=nv,columns=['n.name'],terms=locations)
        q._append_like_group(clauses=mc,values=mv,columns=[c.replace('l.','p.') for c in q.SEARCH_FIELD_COLUMNS['location'] if c.startswith('l.')],terms=locations)
        cte=('WITH RECURSIVE location_names(name) AS ('
             'SELECT MIN(location_name) FROM vocabulary_entries UNION ALL '
             'SELECT (SELECT MIN(location_name) FROM vocabulary_entries WHERE location_name>n.name) '
             'FROM location_names n WHERE n.name IS NOT NULL LIMIT 257), '
             'matched_names AS MATERIALIZED (SELECT n.name FROM location_names n WHERE n.name IS NOT NULL AND '+nc[0]+'), '
             'matched_meta AS MATERIALIZED (SELECT p.user_id,p.location_name FROM vocabulary_locations p WHERE '+mc[0]+') ')
        simple='(e.location_name IN (SELECT name FROM matched_names) OR (e.user_id,e.location_name) IN (SELECT user_id,location_name FROM matched_meta))'
        plan={}
        plan['current']={
            'count':freeze(conn,'SELECT COUNT(*) FROM vocabulary_entries e WHERE '+where,values),
            'page':freeze(conn,f'SELECT {entry}, {loc}FROM (SELECT {entry}, e.user_id FROM vocabulary_entries e WHERE {where} ORDER BY e.id DESC LIMIT 50 OFFSET 0) e {join}ORDER BY e.id DESC',values),
            'all':freeze(conn,f'SELECT {entry}, e.user_id FROM vocabulary_entries e WHERE {where} ORDER BY e.id DESC',values)}
        vals=nv+mv+cv
        plan['identity_or']={
            'count':freeze(conn,cte+'SELECT COUNT(*) FROM vocabulary_entries e WHERE '+simple+' AND '+content,vals),
            'page':freeze(conn,cte+f'SELECT {entry}, {loc}FROM (SELECT {entry}, e.user_id FROM vocabulary_entries e WHERE '+simple+' AND '+content+f' ORDER BY e.id DESC LIMIT 50) e {join}ORDER BY e.id DESC',vals),
            'all':freeze(conn,cte+f'SELECT {entry}, e.user_id FROM vocabulary_entries e WHERE '+simple+' AND '+content+' ORDER BY e.id DESC',vals)}
        branch1='e.location_name IN (SELECT name FROM matched_names) AND '+content
        branch2='(e.user_id,e.location_name) IN (SELECT user_id,location_name FROM matched_meta) AND e.location_name NOT IN (SELECT name FROM matched_names) AND '+content
        union=(f'SELECT {entry}, e.user_id FROM vocabulary_entries e WHERE '+branch1+' UNION ALL '+f'SELECT {entry}, e.user_id FROM vocabulary_entries e WHERE '+branch2)
        vals=nv+mv+cv+cv
        plan['disjoint_union']={
            'count':freeze(conn,cte+'SELECT SUM(c) FROM (SELECT COUNT(*) c FROM vocabulary_entries e WHERE '+branch1+' UNION ALL SELECT COUNT(*) c FROM vocabulary_entries e WHERE '+branch2+')',vals),
            'page':freeze(conn,cte+f'SELECT {entry}, {loc}FROM ('+union+f' ORDER BY id DESC LIMIT 50) e {join}ORDER BY e.id DESC',vals),
            'all':freeze(conn,cte+union+' ORDER BY id DESC',vals)}
        first_source=('matched_names n CROSS JOIN vocabulary_entries e INDEXED BY ix_vocabulary_entries_location_name '
                      'WHERE e.location_name=n.name AND '+content)
        second_source=('matched_meta p CROSS JOIN vocabulary_entries e INDEXED BY idx_vocabulary_entries_user_location '
                       'WHERE e.user_id=p.user_id AND e.location_name=p.location_name '
                       'AND e.location_name NOT IN (SELECT name FROM matched_names) AND '+content)
        union=(f'SELECT {entry}, e.user_id FROM '+first_source+' UNION ALL '+
               f'SELECT {entry}, e.user_id FROM '+second_source)
        plan['location_seek']={
            'count':freeze(conn,cte+'SELECT SUM(c) FROM (SELECT COUNT(*) c FROM '+first_source+
                           ' UNION ALL SELECT COUNT(*) c FROM '+second_source+')',vals),
            'page':freeze(conn,cte+f'SELECT {entry}, {loc}FROM ('+union+
                          f' ORDER BY id DESC LIMIT 50) e {join}ORDER BY e.id DESC',vals),
            'all':freeze(conn,cte+union+' ORDER BY id DESC',vals)}
        estimate_first=('matched_names n CROSS JOIN vocabulary_entries e INDEXED BY ix_vocabulary_entries_location_name '
                        'WHERE e.location_name=n.name')
        estimate_second=('matched_meta p CROSS JOIN vocabulary_entries e INDEXED BY idx_vocabulary_entries_user_location '
                         'WHERE e.user_id=p.user_id AND e.location_name=p.location_name '
                         'AND e.location_name NOT IN (SELECT name FROM matched_names)')
        selector=(cte.rstrip()+', budget AS MATERIALIZED ('
                  'SELECT MIN(32768,MAX(1024,(SELECT COUNT(*) FROM vocabulary_entries)/10)) n) '
                  'SELECT (SELECT COUNT(*) FROM (SELECT 1 FROM '+estimate_first+
                  ' UNION ALL SELECT 1 FROM '+estimate_second+
                  ' LIMIT (SELECT n+1 FROM budget))) <= (SELECT n FROM budget)')
        plan['adaptive']=dict(plan['location_seek'],selector=freeze(conn,selector,nv+mv))
        # Bounded name enumeration is a plan optimization, never a result cap.
        guard=(cte.split('matched_names AS MATERIALIZED')[0].rstrip(', ') +
               ' SELECT EXISTS(SELECT 1 FROM location_names WHERE name IS NOT NULL LIMIT 1 OFFSET 256)')
        for version in plan:
            if version != 'current':
                plan[version]['guard']=guard
                plan[version]['fallback']=dict(plan['current'])
        page_first=set(fields) in ({'headword'},{'definition','headword'}) and q._prefer_location_identity_scan(q=keyword,fields=q.DEFAULT_SEARCH_FIELDS,locations=locations,province=None,city=None,regions=None)
        base=dict(name=scope+'-'+'+'.join(fields)+'-'+keyword,scope=scope,fields=fields,q=keyword,locations=locations)
        jobs.append(dict(base,endpoint='entries',page_first=page_first,plans=plan))
    # Freeze actual aggregate SQL through the existing service functions too.
    aggregate_jobs=[]
    for job in jobs:
        if job['fields'] not in [['definition'],['headword'],['definition','headword']]:
            continue
        for endpoint,func in [('standard-words',q.query_vocabulary_standard_words),('map-points',q.query_vocabulary_map_points)]:
            trace=[]
            conn.set_trace_callback(trace.append)
            func(session=SimpleNamespace(connection=lambda:SimpleNamespace(connection=conn)),
                 q=job['q'],search_fields=job['fields'],locations=job['locations'],
                 **({'limit':None} if endpoint=='standard-words' else {}))
            conn.set_trace_callback(None)
            original=[sql for sql in trace if sql.startswith('SELECT')][-1]
            # Scope candidate already filters content; grouping and metadata
            # association remain exactly the original aggregate statement.
            seek=job['plans']['location_seek']
            full=seek['all']
            prefix,body=full.split('SELECT e.id, e.standard_word',1)
            union='SELECT e.id, e.standard_word'+body
            union=union.removesuffix(' ORDER BY id DESC')
            replacement='FROM ('+union+') e '+("WHERE e.standard_word <> '' " if endpoint=='standard-words' else '')+'GROUP BY'
            aggregate,substitutions=re.subn(r'FROM vocabulary_entries e(?: INDEXED BY \w+)? WHERE .*? GROUP BY',lambda _:replacement,original,count=1)
            assert substitutions==1,(endpoint,original)
            current={'aggregate':original,'all':original}
            adaptive={'aggregate':prefix+aggregate,'all':prefix+aggregate,
                      'guard':seek['guard'],'selector':job['plans']['adaptive']['selector'],'fallback':current}
            aggregate_jobs.append(dict(**{k:v for k,v in job.items() if k not in {'endpoint','page_first','plans'}},
                                       endpoint=endpoint,page_first=False,plans={'current':current,'adaptive':adaptive}))
    jobs.extend(aggregate_jobs)
    (args.work/'jobs.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2))
    (args.work/'jobs').mkdir(exist_ok=True)
    for index,job in enumerate(jobs):
        (args.work/'jobs'/f'{index}.json').write_text(json.dumps(job,ensure_ascii=False))
    print(json.dumps({'jobs':len(jobs),'query_sha256':hashlib.sha256((ROOT/'app/service/vocabulary/query.py').read_bytes()).hexdigest()}))


def choose(conn,plan):
    if plan.get('guard') and conn.execute(plan['guard']).fetchone()[0]:
        return plan['fallback']
    if plan.get('selector') and not conn.execute(plan['selector']).fetchone()[0]:
        return plan['fallback']
    return plan


def execute(conn,plan,page_first,known_total=None):
    if known_total == 0:
        return 0,[]
    plan=choose(conn,plan)
    if 'aggregate' in plan:
        rows=conn.execute(plan['aggregate']).fetchall()
        return len(rows),rows
    if known_total is not None:
        return known_total,conn.execute(plan['page']).fetchall()
    if page_first:
        rows=conn.execute(plan['page']).fetchall()
        total=len(rows) if len(rows)<50 else conn.execute(plan['count']).fetchone()[0]
    else:
        total=conn.execute(plan['count']).fetchone()[0]
        rows=conn.execute(plan['page']).fetchall() if total else []
    return total, rows


def rss():
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value/1024 if sys.platform=='darwin' else value


def child(args):
    job=json.loads((args.work/'jobs'/f'{args.index}.json').read_text())
    conn=readonly(args.db)
    known_total=conn.execute(job['plans']['current']['count']).fetchone()[0] if args.cached_count else None
    statusfile=Path('/proc/self/status')
    def status():
        return {k:int(v.strip().split()[0]) for k,v in (line.split(':',1) for line in statusfile.read_text().splitlines()) if k in {'VmRSS','VmHWM'}} if statusfile.exists() else {}
    pre_status=status()
    start_rss=rss();iofile=Path('/proc/self/io')
    def io():
        return {k:int(v) for k,v in (x.split(': ') for x in iofile.read_text().splitlines())} if iofile.exists() else {}
    before=io(); start=time.perf_counter()
    total,rows=execute(conn,job['plans'][args.plan],job['page_first'],known_total)
    elapsed=(time.perf_counter()-start)*1000;peak=rss();after=io()
    print(json.dumps(dict(first_ms=elapsed,peak_rss_kib=peak,pre_query_peak_rss_kib=start_rss,pre_query_proc_status_kib=pre_status,post_query_proc_status_kib=status(),total=total,returned=len(rows),process_io_delta={k:after[k]-before[k] for k in after})))


def run(args):
    jobs=json.loads((args.work/'jobs.json').read_text())
    conn=readonly(args.db); results=[]
    for index,job in enumerate(jobs):
        if args.only and args.only not in job['name']:
            continue
        if args.endpoint and job['endpoint'] not in args.endpoint.split(','):
            continue
        known_total=conn.execute(job['plans']['current']['count']).fetchone()[0] if args.cached_count else None
        variants=[v for v in job['plans'] if not args.variants or v in args.variants.split(',')];times={v:[] for v in variants}
        expected=None;full_expected=None
        for iteration in range(args.rounds+1):
            for version in (variants if iteration%2==0 else variants[::-1]):
                start=time.perf_counter();value=execute(conn,job['plans'][version],job['page_first'],known_total);elapsed=(time.perf_counter()-start)*1000
                if expected is None:expected=value
                assert value==expected,(job['name'],version,'page or count')
                if iteration:times[version].append(elapsed)
        measurements={}
        for version in variants:
            # Complete ordered record comparison is outside timing, never truncated.
            h=hashlib.sha256();count=0
            chosen=choose(conn,job['plans'][version])
            for row in conn.execute(chosen['all']):h.update(repr(row).encode());count+=1
            full=(count,h.hexdigest())
            assert count==expected[0],(job['name'],version,'full total')
            if full_expected is None:full_expected=full
            assert full==full_expected,(job['name'],version,'full order')
            child_result=subprocess.run([sys.executable,__file__,'--child','--work',str(args.work),'--db',str(args.db),'--index',str(index),'--plan',version]+(['--cached-count'] if args.cached_count else []),capture_output=True,text=True)
            if child_result.returncode:raise RuntimeError(child_result.stderr)
            selected=('no-query-cached-zero' if known_total==0 else
                      'current' if chosen is job['plans'][version].get('fallback') else version)
            measurements[version]=dict(median_ms=statistics.median(times[version]),samples_ms=times[version],selected=selected,fresh_process=json.loads(child_result.stdout),plans={k:conn.execute('EXPLAIN QUERY PLAN '+s).fetchall() for k,s in job['plans'][version].items() if k not in {'all','fallback'}})
        results.append(dict(**{k:v for k,v in job.items() if k!='plans'},count_cache_hit=args.cached_count,total=expected[0],returned=len(expected[1]),full_signature=full_expected,measurements=measurements))
        out=dict(platform=platform.platform(),sqlite=sqlite3.sqlite_version,database=str(args.db),entries=conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0],limits={p:Path('/sys/fs/cgroup/'+p).read_text().strip() for p in ['cpu.max','memory.max','memory.swap.max','memory.peak','memory.events'] if Path('/sys/fs/cgroup/'+p).exists()},results=results)
        args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2))
        print(json.dumps({'endpoint':job['endpoint'],'name':job['name'],'ms':{v:round(x['median_ms'],2) for v,x in measurements.items()},'total':expected[0]},ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--run',action='store_true');p.add_argument('--child',action='store_true');p.add_argument('--work',type=Path,default=WORK);p.add_argument('--db',type=Path);p.add_argument('--output',type=Path);p.add_argument('--rounds',type=int,default=5);p.add_argument('--index',type=int);p.add_argument('--plan');p.add_argument('--variants');p.add_argument('--only');p.add_argument('--endpoint');p.add_argument('--cached-count',action='store_true');a=p.parse_args()
    if a.prepare:prepare(a)
    elif a.child:child(a)
    elif a.run:run(a)

if __name__=='__main__':main()
