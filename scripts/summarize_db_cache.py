"""Validate a completed sweep and emit compact metrics without database contents."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics

BUDGETS = [2000, 4096, 8192, 16000]
RECOMMENDED = {key: 2000 for key in ['query','dialects','characters','yubao','villages',
               'villages_admin','logs','auth','spoken','vocabulary','gis','characters_attach']}
RECOMMENDED['toponyms'] = 4096  # 2GB host: retain 4MiB; 8MiB is a performance option


def median(values):
    return round(statistics.median(values), 6) if values else None


def summarize(rows):
    counts = Counter((r['db'], r['cache_kib']) for r in rows)
    if set(counts) != {(db, budget) for db in RECOMMENDED for budget in BUDGETS}:
        raise ValueError('Incomplete database/budget coverage')
    if set(counts.values()) != {3}:
        raise ValueError('Expected three independent processes per database/budget')
    hashes = defaultdict(set)
    identities = defaultdict(set)
    errors = []
    for row in rows:
        if row['identity_before'] != row['identity_after']:
            raise ValueError('Source file changed during measurement: '+row['db'])
        identities[row['file']].add(tuple(row['identity_before']))
        if row['db']=='characters_attach' and row.get('attach_unique_locations') != 5:
            raise ValueError('ATTACH sample must use five distinct locations')
        for case in row['results']:
            for sample in case['samples']:
                if 'error' in sample:
                    errors.append({'db':row['db'],'cache_kib':row['cache_kib'],'round':row['round'],
                                   'case':case['case'],'phase':case['phase'],'error':sample['error']})
                else:
                    hashes[row['db'],case['case']].add(sample['hash'])
    if any(len(values)!=1 for values in identities.values()):
        raise ValueError('Source file identity changed between processes')
    if any(len(values)!=1 for values in hashes.values()):
        raise ValueError('Result digest differs between budgets/phases/rounds')
    output = {'processes':len(rows),'samples':sum(len(c['samples']) for r in rows for c in r['results']),
              'case_count':len(hashes),'errors':errors,'databases':{}}
    for db, recommend in RECOMMENDED.items():
        output['databases'][db] = {'recommended_kib':recommend, 'budgets':{}}
        for budget in BUDGETS:
            group=[r for r in rows if r['db']==db and r['cache_kib']==budget]
            stats={'rss_one_delta_mib':median([r['rss_one_delta_mib'] for r in group]),
                   'rss_one_range_mib':[min(r['rss_one_delta_mib'] for r in group),max(r['rss_one_delta_mib'] for r in group)],
                   'rss_two_delta_mib':median([r['rss_two_delta_mib'] for r in group]),
                   'peak_rss_mib':max(r['peak_rss_mib'] for r in group),'cases':{}}
            names=[c['case'] for c in group[0]['results'] if c['phase']=='repeated']
            for name in names:
                cstats={}
                for phase in ['first','warm','mixed','concurrent_warm','concurrent_new']:
                    per_process=[]; all_values=[]; cpu=[]
                    for r in group:
                        samples=[]
                        for c in r['results']:
                            if c['case']!=name:continue
                            if phase=='first' and c['phase']=='repeated': samples += c['samples'][:1]
                            if phase=='warm' and c['phase']=='repeated': samples += c['samples'][1:]
                            if phase=='mixed' and c['phase']=='mixed': samples += c['samples']
                            if phase=='concurrent_warm' and c['phase']=='concurrent2': samples += c['samples'][:1]
                            if phase=='concurrent_new' and c['phase']=='concurrent2': samples += c['samples'][1:]
                        success=[s for s in samples if 'error' not in s]
                        values=[s['sql_ms'] for s in success]
                        if values:per_process.append(statistics.median(values))
                        all_values+=values
                        cpu += [s['sql_cpu_ms'] for s in success]
                    cstats[phase]={'median_sql_ms':median(per_process),'samples':len(all_values),
                                   'max_sql_ms':max(all_values) if all_values else None,'median_sql_cpu_ms':median(cpu)}
                stats['cases'][name]=cstats
            output['databases'][db]['budgets'][str(budget)]=stats
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args()
    output=summarize(json.loads(args.input.read_text()))
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(f"validated {output['processes']} processes / {output['samples']} samples / {output['case_count']} cases; errors={len(output['errors'])}")


if __name__=='__main__':main()
