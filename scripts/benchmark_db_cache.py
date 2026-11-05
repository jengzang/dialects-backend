"""Read-only local SQLite page-cache sweep; does not import/start the application.

Run one database/budget in a fresh process. SQL comes from the runtime query
shapes named in each case, with bounded examples; this is not an HTTP benchmark.
Main/attached database files always use mode=ro. TEMP tables remain connection
local, matching notes; no WAL, index, migration, or persistent PRAGMA writes.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
from pathlib import Path
import resource
import sqlite3
import statistics
import subprocess
import sys
import threading
import time

FILES = {
    'query': 'query_user.db', 'dialects': 'dialects_user.db', 'characters': 'characters.db',
    'yubao': 'yubao.db', 'villages': 'villages.db', 'villages_admin': 'villages_admin.db',
    'logs': 'logs.db', 'auth': 'auth.db', 'spoken': 'yc_spoken.db',
    'vocabulary': 'vocabulary.db', 'toponyms': 'toponyms.db', 'gis': 'dependency/gis.db',
    'characters_attach': 'dialects_user.db',
}
CHARS = list('一二三四五六七八九十天地人山水日月大小中')


def qi(value):
    return '"' + value.replace('"', '""') + '"'


def rss_mib():
    if sys.platform.startswith('linux'):
        return int(next(x.split()[1] for x in Path('/proc/self/status').read_text().splitlines()
                        if x.startswith('VmRSS:'))) / 1024
    return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(__import__('os').getpid())], text=True)) / 1024


def identity(path):
    stat = path.stat()
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]


def connect(root, db, cache):
    path = (root / FILES[db]).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, check_same_thread=False, timeout=.1)
    try:
        # Hold all other settings constant across budgets. FILE is the runtime
        # profile for GIS/toponyms; legacy generic pools use MEMORY.
        conn.execute('PRAGMA temp_store=' + ('FILE' if db in {'gis', 'toponyms'} else 'MEMORY'))
        conn.execute(f'PRAGMA main.cache_size=-{cache if db != "characters_attach" else 16000}')
        if db == 'characters_attach':
            conn.execute('ATTACH DATABASE ? AS chars_db',
                         ((root / 'characters.db').resolve(strict=True).as_uri() + '?mode=ro',))
            conn.execute(f'PRAGMA chars_db.cache_size=-{cache}')
            assert conn.execute('PRAGMA chars_db.cache_size').fetchone()[0] == -cache
        else:
            assert conn.execute('PRAGMA main.cache_size').fetchone()[0] == -cache
        return conn
    except BaseException:
        conn.close()
        raise


def cases(conn, db):
    """Return (label, [(sql, params), ...]); all samples are reproducible."""
    result = []
    def add(label, sql, params=()):
        result.append((label, [(sql, tuple(params))]))
    def multi(label, steps):
        result.append((label, steps))
    def sample(sql):
        return [row[0] for row in conn.execute(sql).fetchall()]
    def placeholders(values):
        return ','.join('?' for _ in values)
    if db == 'query':
        locs = sample('SELECT 簡稱 FROM dialects WHERE 簡稱 IS NOT NULL ORDER BY 簡稱 LIMIT 20')
        add('location_detail_batch20', 'SELECT 簡稱,語言,音典分區,地圖集二分區,經緯度 FROM dialects WHERE 簡稱 IN ('+placeholders(locs)+') ORDER BY 簡稱', locs)
        add('map_points_all', 'SELECT 簡稱,經緯度,地圖集二分區,音典分區,方言島 FROM dialects WHERE TRIM(COALESCE(簡稱,""))<>""')
        add('partition_group', 'SELECT 音典分區,COUNT(*) FROM dialects GROUP BY 音典分區 ORDER BY 音典分區')
    elif db in {'characters', 'characters_attach'}:
        if db == 'characters_attach':
            with closing(sqlite3.connect((ROOT / 'query_user.db').as_uri()+'?mode=ro', uri=True)) as query:
                locs = [r[0] for r in query.execute('SELECT DISTINCT 簡稱 FROM dialects WHERE 簡稱 IS NOT NULL ORDER BY 簡稱 LIMIT 5')]
            if len(set(locs)) != 5:
                raise ValueError('ATTACH workload requires five distinct locations')
            add('matrix_join_5_locations', 'SELECT d.漢字,d.聲母,c.攝,c.組,c.韻 FROM dialects d JOIN chars_db.characters c ON d.漢字=c.漢字 WHERE d.簡稱 IN ('+placeholders(locs)+') AND d.聲母 IS NOT NULL AND c.攝 IS NOT NULL AND c.組 IS NOT NULL AND c.韻 IS NOT NULL', locs)
        else:
            add('batch20_characters', 'SELECT 漢字,攝,呼,等,韻,調,組,母 FROM characters WHERE 漢字 IN ('+placeholders(CHARS)+') ORDER BY 漢字,攝,呼,等,韻,調,組,母', CHARS)
            add('batch20_full_rows', 'SELECT * FROM characters WHERE 漢字 IN ('+placeholders(CHARS)+')', CHARS)
            add('hierarchy_知組三等', 'SELECT 漢字 FROM characters WHERE 組=? AND 等 IN (?,?,?,?) ORDER BY 漢字', ['知','三A','三B','三C','三銳'])
            multi('hierarchy_distincts', [('SELECT DISTINCT '+qi(col)+' FROM characters WHERE '+qi(col)+' IS NOT NULL AND TRIM('+qi(col)+")<>'' ORDER BY "+qi(col), ()) for col in ['攝','呼','等','韻','調','系','組','母','部位','方式']])
            multi('six_tables_batch20', [('SELECT 漢字 FROM '+qi(t)+' WHERE 漢字 IN ('+placeholders(CHARS)+') ORDER BY 漢字', CHARS) for t in ['characters','hongwu','menggu','old_chinese','zhongyuan','fenyun']])
    elif db == 'dialects':
        locs = sample('SELECT 簡稱 FROM dialects WHERE 簡稱 IS NOT NULL ORDER BY rowid LIMIT 1')
        # Derive additional locations from the small query database, not a full
        # DISTINCT/sort of the 2.6GiB dialect table during setup.
        with closing(sqlite3.connect((ROOT / 'query_user.db').as_uri()+'?mode=ro', uri=True)) as query:
            locs = [r[0] for r in query.execute('SELECT 簡稱 FROM dialects WHERE 簡稱 IS NOT NULL ORDER BY 簡稱 LIMIT 20')]
        add('chars20_locations20', 'SELECT 簡稱,漢字,聲母,韻母,聲調 FROM dialects WHERE 簡稱 IN ('+placeholders(locs)+') AND 漢字 IN ('+placeholders(CHARS)+')', locs+CHARS)
        multi('feature_count_locations20', [('SELECT 簡稱,'+col+',COUNT(DISTINCT 漢字) FROM dialects WHERE 簡稱 IN ('+placeholders(locs)+') GROUP BY 簡稱,'+col, locs) for col in ['聲母','韻母','聲調']])
        multi('notes_fts_temp_count_page', [
            ('DROP TABLE IF EXISTS temp.matched_rowids', ()),
            ('CREATE TEMP TABLE matched_rowids AS SELECT notes.rowid FROM notes_fts JOIN notes ON notes.rowid=notes_fts.rowid WHERE notes_fts MATCH ? AND TRIM(COALESCE(notes.註釋,"")) NOT IN ("","_","-")', ('"上 面"',)),
            ('SELECT COUNT(*) FROM matched_rowids', ()),
            ('SELECT notes.rowid,notes.簡稱,notes.漢字,notes.音節,notes.註釋 FROM notes JOIN matched_rowids ON notes.rowid=matched_rowids.rowid ORDER BY notes.rowid LIMIT 50', ()),
            ('DROP TABLE temp.matched_rowids', ()),
        ])
        add('notes_pronunciation_count', 'SELECT COUNT(*) FROM notes WHERE COALESCE(音節,"") LIKE ? AND TRIM(COALESCE(註釋,"")) NOT IN ("","_","-")', ('%a%',))
    elif db == 'yubao':
        word = sample('SELECT word FROM vocabulary WHERE word IS NOT NULL AND TRIM(word)<>"" ORDER BY word LIMIT 1')[0]
        sentence = sample('SELECT sentence FROM grammar WHERE sentence IS NOT NULL AND TRIM(sentence)<>"" ORDER BY sentence LIMIT 1')[0]
        multi('word_detail_count_page50', [('SELECT COUNT(*) FROM vocabulary WHERE word=?', (word,)), ('SELECT * FROM vocabulary WHERE word=? ORDER BY id LIMIT 50', (word,))])
        add('all_words_default', 'SELECT DISTINCT word FROM vocabulary WHERE word IS NOT NULL AND TRIM(word)<>"" ORDER BY word')
        add('distinct_word_count', 'SELECT COUNT(DISTINCT word) FROM vocabulary WHERE word IS NOT NULL AND TRIM(word)<>""')
        multi('grammar_detail_count_page50', [('SELECT COUNT(*) FROM grammar WHERE sentence=?',(sentence,)),('SELECT * FROM grammar WHERE sentence=? ORDER BY id LIMIT 50',(sentence,))])
        add('all_sentences', 'SELECT DISTINCT sentence FROM grammar WHERE sentence IS NOT NULL AND TRIM(sentence)<>"" ORDER BY sentence')
    elif db == 'villages':
        add('overview', 'SELECT * FROM metadata_overview_stats')
        add('regional_ngram_count', 'SELECT COUNT(*) FROM regional_ngram_frequency')
        add('ngram_significance_group', 'WITH level_before AS (SELECT region_level AS level,SUM(total_before_filter) AS total_before FROM (SELECT DISTINCT region_level,region_name,total_before_filter FROM ngram_significance) GROUP BY region_level) SELECT ns.region_level,COUNT(*),SUM(CASE WHEN ns.p_value<0.05 THEN 1 ELSE 0 END),lb.total_before FROM ngram_significance ns JOIN level_before lb ON ns.region_level=lb.level GROUP BY ns.region_level ORDER BY ns.region_level')
        add('village_contains_page100', 'SELECT village_id,自然村_去前缀,longitude,latitude FROM 广东省自然村_预处理 WHERE 自然村_去前缀 LIKE ? ORDER BY village_id LIMIT 100', ('%山%',))
    elif db == 'villages_admin':
        add('sql_count_gd', 'SELECT COUNT(*) FROM gd')
        add('sql_page100_gd', 'SELECT city,district,town,natural_village,longitude,latitude FROM gd ORDER BY rowid LIMIT 100')
        add('sql_filtered_count', 'SELECT COUNT(*) FROM toponyms WHERE standard_name LIKE ?', ('%山%',))
    elif db == 'logs':
        add('total_visits', 'SELECT SUM(count) FROM api_visit_log WHERE date IS NULL')
        add('daily_trend30', 'SELECT date,SUM(call_count) FROM api_usage_daily WHERE date >= (SELECT date(MAX(date),"-30 days") FROM api_usage_daily) GROUP BY date ORDER BY date')
        add('top_keywords', 'SELECT value,COUNT(*) AS n FROM api_keyword_log GROUP BY value ORDER BY n DESC,value LIMIT 10')
        add('diagnostics_latest50', 'SELECT id,occurred_at,event_type,path,status_code,duration_ms FROM api_diagnostic_events ORDER BY id DESC LIMIT 50')
    elif db == 'auth':
        add('usage_totals', 'SELECT COUNT(*),COUNT(DISTINCT user_id),COUNT(DISTINCT ip) FROM api_usage_logs')
        add('usage_by_path', 'SELECT path,COUNT(*),AVG(duration) FROM api_usage_logs GROUP BY path ORDER BY path')
        add('user_counts', 'SELECT role,status,COUNT(*) FROM users GROUP BY role,status ORDER BY role,status')
    elif db == 'spoken':
        add('generic_count', 'SELECT COUNT(*) FROM 口语字')
        add('generic_page100', 'SELECT 本字考,IPA,粤拼,词性,释义 FROM 口语字 ORDER BY rowid LIMIT 100')
        add('generic_like', 'SELECT 本字考,IPA,释义 FROM 口语字 WHERE 释义 LIKE ? ORDER BY rowid LIMIT 100', ('%人%',))
    elif db == 'vocabulary':
        add('sql_count', 'SELECT COUNT(*) FROM vocabulary_entries')
        add('sql_page50', 'SELECT id,location_name,standard_word,local_expression,ipa FROM vocabulary_entries ORDER BY id LIMIT 50')
        add('sql_fuzzy_count', 'SELECT COUNT(*) FROM vocabulary_entries WHERE standard_word LIKE ? OR local_expression LIKE ?', ('%路%','%路%'))
        add('sql_standard_words', 'SELECT DISTINCT standard_word FROM vocabulary_entries WHERE standard_word LIKE ? ORDER BY standard_word LIMIT 50', ('%路%',))
    elif db == 'toponyms':
        add('names_contains20', 'SELECT DISTINCT standard_name FROM single WHERE place_type_code IN (?) AND standard_name LIKE ? AND TRIM(COALESCE(standard_name,""))<>"" ORDER BY standard_name LIMIT 20', ('22200','%村%'))
        add('points_prefix5000', 'SELECT id,longitude,latitude FROM single WHERE place_type_code IN (?) AND standard_name>=? AND standard_name<? AND standard_name LIKE ? ORDER BY id LIMIT 5001', ('22200','大','太','大%'))
        add('divisions_children', 'SELECT code,name,level,COALESCE(single_cnt,0) FROM divisions WHERE parent_code=? ORDER BY code', ('44',))
    elif db == 'gis':
        add('search_beijing', 'SELECT id,pid,deep,name,ext_path FROM features WHERE LOWER(name) LIKE ? OR LOWER(ext_path) LIKE ? ORDER BY id', ('%北京%','%北京%'))
        add('children_beijing', 'SELECT id,pid,deep,name FROM features WHERE pid=? ORDER BY deep,id', (11,))
        add('bbox_candidates', 'SELECT sub_id FROM subgeometry_rtree WHERE min_lng<=? AND max_lng>=? AND min_lat<=? AND max_lat>=? ORDER BY sub_id', (116.4074,116.4074,39.9042,39.9042))
        add('boundary_blobs', 'SELECT sub_id,geom_blob FROM subgeometries WHERE feature_id=? ORDER BY sub_id', (110101,))
    return result


def run_case(conn, case, seconds):
    deadline = time.monotonic() + seconds
    conn.set_progress_handler(lambda: time.monotonic() >= deadline, 1000)
    wall, cpu = time.perf_counter(), time.thread_time()
    sql_ms = sql_cpu_ms = 0.0
    digest = hashlib.sha256()
    counts = []
    try:
        for sql, params in case[1]:
            count = 0
            sql_wall, sql_cpu = time.perf_counter(), time.thread_time()
            cursor = conn.execute(sql, params)
            sql_ms += (time.perf_counter()-sql_wall)*1000
            sql_cpu_ms += (time.thread_time()-sql_cpu)*1000
            try:
                while True:
                    sql_wall, sql_cpu = time.perf_counter(), time.thread_time()
                    rows = cursor.fetchmany(32)
                    sql_ms += (time.perf_counter()-sql_wall)*1000
                    sql_cpu_ms += (time.thread_time()-sql_cpu)*1000
                    if not rows:
                        break
                    for row in rows:
                        for value in row:
                            digest.update(type(value).__name__.encode()+b':')
                            digest.update(value if isinstance(value,bytes) else str(value).encode())
                            digest.update(b'\0')
                        count += 1
            finally:
                cursor.close()
            counts.append(count)
        return {'ms': (time.perf_counter()-wall)*1000, 'cpu_ms': (time.thread_time()-cpu)*1000, 'sql_ms': sql_ms, 'sql_cpu_ms': sql_cpu_ms,
                'rows': counts, 'hash': digest.hexdigest()}
    except sqlite3.Error as exc:
        return {'ms': (time.perf_counter()-wall)*1000, 'cpu_ms': (time.thread_time()-cpu)*1000, 'sql_ms': sql_ms, 'sql_cpu_ms': sql_cpu_ms,
                'error': type(exc).__name__+': '+str(exc)}
    finally:
        conn.set_progress_handler(None,0)
        if conn.in_transaction:
            conn.rollback()


def main():
    global ROOT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--db',choices=FILES,required=True)
    parser.add_argument('--cache-kib',type=int,choices=[2000,4096,8192,16000],required=True)
    parser.add_argument('--runs',type=int,choices=range(1,8),default=4)
    parser.add_argument('--timeout',type=float,default=3)
    args=parser.parse_args()
    if not 0 < args.timeout <= 5: parser.error('timeout must be >0 and <=5')
    ROOT=args.data_dir.resolve(strict=True)
    path=(ROOT/FILES[args.db]).resolve(strict=True)
    before=identity(path)
    baseline=rss_mib()
    conn=connect(ROOT,args.db,args.cache_kib)
    second=None
    try:
        workload=cases(conn,args.db)
        result=[]
        # First query on each shape, then same-connection repeated workload.
        for case in workload:
            samples=[run_case(conn,case,args.timeout) for _ in range(args.runs)]
            result.append({'case':case[0], 'phase':'repeated','samples':samples})
        rss_one=rss_mib()
        for cycle in range(2):
            for case in workload:
                result.append({'case':case[0],'phase':'mixed','cycle':cycle,
                               'samples':[run_case(conn,case,args.timeout)]})
        second=connect(ROOT,args.db,args.cache_kib)
        # Worker-local connections are exclusive. Two test threads max; the
        # script never creates extra application workers or runs on production.
        with ThreadPoolExecutor(max_workers=2) as executor:
            for case in workload:
                gate=threading.Barrier(2)
                def operation(dbconn):
                    gate.wait(timeout=5)
                    return run_case(dbconn,case,args.timeout)
                # Futures must be submitted before waiting on either barrier.
                futures=[executor.submit(operation,dbconn) for dbconn in (conn,second)]
                samples=[future.result(timeout=args.timeout*len(case[1])+10) for future in futures]
                result.append({'case':case[0],'phase':'concurrent2','connection_states':['warm','new'],'samples':samples})
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(json.dumps({'db':args.db,'cache_kib':args.cache_kib,'sqlite_version':sqlite3.sqlite_version,
                          'file':str(path),'file_mib':path.stat().st_size/1024**2,
                          'identity_before':before,'identity_after':identity(path),
                          'rss_baseline_mib':baseline,'rss_one_delta_mib':rss_one-baseline,
                          'rss_two_delta_mib':rss_mib()-baseline,
                          'peak_rss_mib':peak/(1024**2 if sys.platform=='darwin' else 1024),
                          'runs':args.runs,'timeout_seconds':args.timeout,'timeout_scope':'whole case, including hashing',
                          'attach_unique_locations':5 if args.db=='characters_attach' else None,'results':result}))
    finally:
        conn.close()
        if second is not None: second.close()


if __name__=='__main__':
    main()
