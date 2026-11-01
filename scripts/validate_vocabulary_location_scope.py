"""Functional checks for the offline scope prototype; no server access/writes."""
import argparse
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('scope_experiment',ROOT/'scripts/benchmark_vocabulary_location_scope.py')
b=importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def semantic(args):
    jobs=json.loads((args.work/'jobs.json').read_text())
    src=b.readonly(args.schema)
    conn=sqlite3.connect(':memory:')
    for sql, in src.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND tbl_name IN ('vocabulary_entries','vocabulary_locations') ORDER BY type DESC"):
        conn.execute(sql)
    src.close()
    names=['天柱竹林','息烽','廣州白話','香港客家話','廣西孤立地点','同名地点']
    for user in [1,2]:
        for name in names:
            if name!='廣西孤立地点':
                conn.execute("INSERT INTO vocabulary_locations(user_id,location_name,coordinates,province,city) VALUES(?,?,'1,2',?,NULL)",(user,name,'廣西' if user==1 else '廣東'))
            for i in range(55):
                conn.execute('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa,notes,informations) VALUES(?,?,?,?,?,?,?)',(user,name,'蜘蛛 人','蜘蛛 人','a',None,''))
    checks=0
    for phase in ['normal','over256']:
        if phase=='over256':
            for i in range(350):
                conn.execute("INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(1,?,'人 蜘蛛','人','a')",('AAA%03d'%i,))
        for job in jobs:
            expected=b.execute(conn,job['plans']['current'],job['page_first'])
            all_expected=conn.execute(job['plans']['current']['all']).fetchall()
            assert len(all_expected)==expected[0]
            for version,plan in job['plans'].items():
                assert b.execute(conn,plan,job['page_first'])==expected,(phase,job['name'],version)
                assert conn.execute(b.choose(conn,plan)['all']).fetchall()==all_expected,(phase,job['name'],version,'full')
                checks+=1
    print(json.dumps({'semantic_checks':checks,'includes':'same names across users, metadata/name overlap, orphan, null fields, full pages, >256 distinct names fallback'},ensure_ascii=False))
    conn.close()


def services(args):
    from app.service.vocabulary import query as q
    conn=b.readonly(args.schema)
    session=lambda connection:SimpleNamespace(connection=lambda:SimpleNamespace(connection=connection))
    checks=0
    class ProxyCursor:
        def __init__(self,original,chosen):
            self.raw=conn.cursor();self.original=original;self.chosen=chosen;self.replaced=0
        def execute(self,sql,values=()):
            if not sql.startswith('SELECT'):
                self.raw.execute(sql,values)
                return self
            expanded=b.freeze(conn,sql,values)
            kind=next((key for key in ['aggregate','count','page'] if expanded==self.original.get(key)),None)
            assert kind is not None,('Unexpected query',expanded)
            self.replaced+=1
            self.raw.execute(self.chosen[kind])
            return self
        def __getattr__(self,name):return getattr(self.raw,name)
        def __iter__(self):return iter(self.raw)
    for job in json.loads((args.work/'jobs.json').read_text()):
        func={'entries':q.query_vocabulary_items,'standard-words':q.query_vocabulary_standard_words,
              'map-points':q.query_vocabulary_map_points}[job['endpoint']]
        params=dict(q=job['q'],search_fields=job['fields'],locations=job['locations'])
        if job['endpoint']=='standard-words':params['limit']=None
        expected=func(session=session(conn),**params)
        chosen=b.choose(conn,job['plans']['adaptive'])
        cursor=ProxyCursor(job['plans']['current'],chosen)
        result=func(session=session(SimpleNamespace(cursor=lambda:cursor)),**params)
        assert cursor.replaced>=1
        assert result==expected,(job['endpoint'],job['name'])
        checks+=1
    conn.close()
    print(json.dumps({'complete_service_dataclass_checks':checks}))


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=b.WORK);p.add_argument('--schema',type=Path,default=ROOT/'outputs/vocabulary-release-20261101/current.db');p.add_argument('--services',action='store_true');a=p.parse_args()
    services(a) if a.services else semantic(a)

if __name__=='__main__':main()
